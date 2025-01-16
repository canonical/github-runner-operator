#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Collection of functions related to health checks for a runner VM."""

import logging
from datetime import datetime, timedelta

import invoke
from fabric import Connection as SSHConnection

from github_runner_manager.errors import KeyfileError, OpenstackHealthCheckError, SSHError
from github_runner_manager.manager.cloud_runner_manager import CloudInitStatus, CloudRunnerState
from github_runner_manager.openstack_cloud.constants import (
    METRICS_EXCHANGE_PATH,
    RUNNER_LISTENER_PROCESS,
    RUNNER_WORKER_PROCESS,
)
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud, OpenstackInstance
from github_runner_manager.utilities import retry

logger = logging.getLogger(__name__)

INSTANCE_IN_BUILD_MODE_TIMEOUT_IN_HOURS = 1

_HealthCheckResult = bool | None  # None indicates that the check can not determine health status


class _SSHError(Exception):
    """Error on SSH command execution."""


def check_runner(openstack_cloud: OpenstackCloud, instance: OpenstackInstance) -> bool:
    """Run a general health check on a runner instance.

    This check applies to runners in any OpenStack state (ACTIVE, STOPPED, etc).

    Args:
        openstack_cloud: The OpenstackCloud instance to use
        instance: The instance hosting the runner to run health check on.

    Returns:
        True if runner is healthy.
    """
    if (check_ok := _health_check_cloud_state(instance)) is not None:
        return check_ok

    try:
        ssh_conn = _get_ssh_connection(openstack_cloud=openstack_cloud, instance=instance)
    except KeyfileError:
        logger.exception(
            "Health check failed due to unable to find keyfile for %s", instance.server_name
        )
        # KeyfileError indicates that we'll never be able to ssh into the unit,
        # so we mark it as unhealthy.
        return False
    except _SSHError:
        logger.exception(
            "Unable to get SSH connection for instance %s, marking as unhealthy.",
            instance.server_name,
        )
        # We assume that the failure to get the SSH connection is not transient, and mark
        # the runner as unhealthy.
        # It is debatable whether we should throw an exception here instead.
        return False

    return check_active_runner(ssh_conn, instance)


def check_active_runner(
    ssh_conn: SSHConnection, instance: OpenstackInstance, accept_finished_job: bool = False
) -> bool:
    """Run a health check for a runner whose openstack instance is ACTIVE.

    Args:
        ssh_conn: The SSH connection to the runner.
        instance: The OpenStack instance to conduit the health check.
        accept_finished_job: Whether a job that has finished should be marked healthy.
            This is useful for runners in construction whose job has already finished
            while the code is still waiting for the runner to be fully operational. Without
            the flag, the health check would fail as it checks for running processes
            which would not be present in this case.

    Raises:
        OpenstackHealthCheckError: If the health check could not be completed.

    Returns:
        Whether the runner should be considered healthy.
    """
    try:
        if (check_ok := _run_health_check_runner_installed(ssh_conn, instance)) is not None:
            return check_ok

        if (
            check_ok := _run_health_check_cloud_init(
                ssh_conn, instance.server_name, accept_finished_job
            )
        ) is not None:
            return check_ok

        if (
            check_ok := _run_health_check_runner_processes_running(ssh_conn, instance.server_name)
        ) is not None:
            return check_ok
    except _SSHError as exc:
        raise OpenstackHealthCheckError(
            "Health check execution failed due to SSH command failure."
        ) from exc

    return True


@retry(exception=SSHError, tries=3, delay=5, backoff=2, local_logger=logger)
def _get_ssh_connection(
    openstack_cloud: OpenstackCloud, instance: OpenstackInstance
) -> SSHConnection:
    """Check whether runner is healthy.

    Args:
        openstack_cloud: The OpenstackCloud instance to use
        instance: The OpenStack instance to conduit the health check.

    Raises:
        _SSHError: Unable to get a SSH connection to the instance.

    Returns:
        Whether the runner is healthy.
    """
    try:
        ssh_conn = openstack_cloud.get_ssh_connection(instance)

    except SSHError as exc:
        raise _SSHError(f"Unable to get SSH connection to {instance.server_name}") from exc
    return ssh_conn


def _health_check_cloud_state(instance: OpenstackInstance) -> _HealthCheckResult:
    """Check the cloud state of the instance to decide if an instance is healthy.

    Args:
        instance: The OpenStack instance to conduit the health check.

    Returns:
        Whether the runner should be considered healthy or None.
    """
    cloud_state = CloudRunnerState.from_openstack_server_status(instance.status)
    logger.debug("Cloud state of %s: %s", instance.server_name, cloud_state)
    if cloud_state in (
        CloudRunnerState.DELETED,
        CloudRunnerState.STOPPED,
    ):
        return False

    if cloud_state in (CloudRunnerState.ERROR, CloudRunnerState.UNKNOWN):
        logger.error(
            "Instance in unexpected status, failing health check. %s: %s (%s)",
            cloud_state,
            instance.server_name,
            instance.server_id,
        )
        return False
    if cloud_state in (CloudRunnerState.CREATED,):
        if datetime.now() - instance.created_at >= timedelta(
            hours=INSTANCE_IN_BUILD_MODE_TIMEOUT_IN_HOURS
        ):
            logger.error(
                "Instance in created status for too long, failing health check. %s: %s (%s)",
                cloud_state,
                instance.server_name,
                instance.server_id,
            )
            return False
        return True
    return None


def _run_health_check_cloud_init(
    ssh_conn: SSHConnection, server_name: str, accept_finished_job: bool = False
) -> _HealthCheckResult:
    """Check cloud-init status to decide if a run is healthy.

    Args:
        ssh_conn: The SSH connection to the runner.
        server_name: The name of the server.
        accept_finished_job: Whether a job that has finished should be marked healthy.

    Returns:
        Whether the cloud-init status indicates the run is healthy or None.
    """
    result: invoke.runners.Result = _execute_ssh_command(ssh_conn, "cloud-init status")
    if not result.ok:
        logger.warning("cloud-init status command failed on %s: %s.", server_name, result.stderr)
        return False

    if CloudInitStatus.DONE in result.stdout:
        return accept_finished_job

    return None


def _run_health_check_runner_installed(
    ssh_conn: SSHConnection, instance: OpenstackInstance
) -> _HealthCheckResult:
    """Check if the runner has already been finishing installing to decide if a run is healthy.

    If the runner has not been installed but is active for a long time, the run is considered
    unhealthy.

    Explanation:
     In reactive mode we use a separate process to spawn the runner, the server might be
     ACTIVE but the runner process is not running yet. We therefore check for the existence
     of the runner-installed.timestamp and assume the runner to be healthy if it does
     does not exist. This is a temporary solution until we have a better way to check
     the runner process, as there might still be a race condition (between writing the
     timestamp and actually starting the runner) that could cause the runner to be marked
     as unhealthy.

    Args:
        ssh_conn: The SSH connection to the runner.
        instance: The OpenStack instance to conduit the health check.

    Returns:
        If the run can be considered healthy depending on the existence of
        the runner-installed.timestamp.
    """
    result = _execute_ssh_command(
        ssh_conn, f"[ -f {METRICS_EXCHANGE_PATH}/runner-installed.timestamp ]"
    )
    if not result.ok:
        logger.info(
            "Runner installed timestamp file not found on %s, cloud-init may still run",
            instance.server_name,
        )
        if datetime.now() - instance.created_at >= timedelta(
            hours=INSTANCE_IN_BUILD_MODE_TIMEOUT_IN_HOURS
        ):
            logger.error(
                "Instance in building status for too long, failing health check. %s (%s)",
                instance.server_name,
                instance.server_id,
            )
            return False
        return True
    return None


def _run_health_check_runner_processes_running(
    ssh_conn: SSHConnection, server_name: str
) -> _HealthCheckResult:
    """Check if the runner processes are running to decide if a run is healthy.

    Args:
        ssh_conn: The SSH connection to the runner.
        server_name: The name of the server.

    Returns:
        If the run can be considered healthy depending on the existence of the processes.
    """
    result = _execute_ssh_command(ssh_conn, "ps aux")
    if not result.ok:
        logger.warning("SSH run of `ps aux` failed on %s: %s", server_name, result.stderr)
        return False
    if RUNNER_WORKER_PROCESS not in result.stdout and RUNNER_LISTENER_PROCESS not in result.stdout:
        logger.warning("Runner process not found on %s", server_name)
        return False
    return None


def _execute_ssh_command(ssh_conn: SSHConnection, command: str) -> invoke.runners.Result:
    """Run a command on the remote server.

    Args:
        ssh_conn: The SSH connection to the runner.
        command: The command to run.

    Returns:
        The result of the command.

    Raises:
        _SSHError: If the command execution failed.
    """
    try:
        return ssh_conn.run(command, warn=True, timeout=30)
    except invoke.exceptions.CommandTimedOut as exc:
        raise _SSHError(
            f"SSH command execution timed out for command '{command}' on {ssh_conn.host}"
        ) from exc
