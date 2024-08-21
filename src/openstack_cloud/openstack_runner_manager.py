# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for self-hosted runner on OpenStack."""

import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import invoke
import jinja2
import paramiko
import paramiko.ssh_exception
from fabric import Connection as SSHConnection

from charm_state import GithubOrg
from errors import (
    CreateMetricsStorageError,
    GetMetricsStorageError,
    IssueMetricEventError,
    KeyfileError,
    OpenStackError,
    RunnerCreateError,
    RunnerStartError,
    SSHError,
)
from manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    GitHubRunnerConfig,
    InstanceId,
    SupportServiceConfig,
)
from manager.runner_manager import HealthState
from metrics import events as metric_events
from metrics import runner as runner_metrics
from metrics import storage as metrics_storage
from openstack_cloud.openstack_cloud import OpenstackCloud, OpenstackInstance
from openstack_cloud.openstack_manager import GithubRunnerRemoveError
from repo_policy_compliance_client import RepoPolicyComplianceClient
from utilities import retry

logger = logging.getLogger(__name__)

BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"
_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"
MAX_METRICS_FILE_SIZE = 1024

RUNNER_STARTUP_PROCESS = "/home/ubuntu/actions-runner/run.sh"
RUNNER_LISTENER_PROCESS = "Runner.Listener"
RUNNER_WORKER_PROCESS = "Runner.Worker"
CREATE_SERVER_TIMEOUT = 5 * 60


class _PullFileError(Exception):
    """Represents an error while pulling a file from the runner instance."""


@dataclass
class OpenStackCloudConfig:
    """Configuration for OpenStack cloud authorisation information.

    Attributes:
        clouds_config: The clouds.yaml.
        cloud: The cloud name to connect to.
    """

    clouds_config: dict[str, dict]
    cloud: str


@dataclass
class OpenStackServerConfig:
    """Configuration for OpenStack server.

    Attributes:
        image: The image name for runners to use.
        flavor: The flavor name for runners to use.
        network: The network name for runners to use.
    """

    image: str
    flavor: str
    network: str


@dataclass
class _RunnerHealth:
    """Runners with health state.

    Attributes:
        healthy: The list of healthy runners.
        unhealthy:  The list of unhealthy runners.
    """

    healthy: tuple[OpenstackInstance, ...]
    unhealthy: tuple[OpenstackInstance, ...]


class OpenstackRunnerManager(CloudRunnerManager):
    """Manage self-hosted runner on OpenStack cloud.

    Attributes:
        name_prefix: The name prefix of the runners created.
    """

    # Ignore "Too many arguments", as the class requires a lot of configurations.
    def __init__(  # pylint: disable=R0913
        self,
        prefix: str,
        cloud_config: OpenStackCloudConfig,
        server_config: OpenStackServerConfig,
        runner_config: GitHubRunnerConfig,
        service_config: SupportServiceConfig,
    ) -> None:
        """Construct the object.

        Args:
            prefix: The prefix to runner name.
            cloud_config: The configuration for OpenStack authorisation.
            server_config: The configuration for creating OpenStack server.
            runner_config: The configuration for the runner.
            service_config: The configuration of supporting services of the runners.
        """
        self._prefix = prefix
        self._cloud_config = cloud_config
        self._server_config = server_config
        self._runner_config = runner_config
        self._service_config = service_config
        self._openstack_cloud = OpenstackCloud(
            clouds_config=self._cloud_config.clouds_config,
            cloud=self._cloud_config.cloud,
            prefix=self.name_prefix,
        )

    @property
    def name_prefix(self) -> str:
        """The prefix of runner names.

        Returns:
            The prefix of the runner names managed by this class.
        """
        return self._prefix

    def create_runner(self, registration_token: str) -> InstanceId:
        """Create a self-hosted runner.

        Args:
            registration_token: The GitHub registration token for registering runners.

        Raises:
            RunnerCreateError: Unable to create runner due to OpenStack issues.

        Returns:
            Instance ID of the runner.
        """
        start_timestamp = time.time()
        instance_id = OpenstackRunnerManager._generate_instance_id()
        instance_name = self._openstack_cloud.get_server_name(instance_id=instance_id)
        cloud_init = self._generate_cloud_init(
            instance_name=instance_name, registration_token=registration_token
        )
        try:
            instance = self._openstack_cloud.launch_instance(
                instance_id=instance_id,
                image=self._server_config.image,
                flavor=self._server_config.flavor,
                network=self._server_config.network,
                cloud_init=cloud_init,
            )
        except OpenStackError as err:
            raise RunnerCreateError(f"Failed to create {instance_name} openstack runner") from err

        self._wait_runner_startup(instance)
        self._wait_runner_running(instance)

        end_timestamp = time.time()
        OpenstackRunnerManager._issue_runner_installed_metric(
            name=instance_name,
            flavor=self.name_prefix,
            install_start_timestamp=start_timestamp,
            install_end_timestamp=end_timestamp,
        )
        return instance_id

    def get_runner(self, instance_id: InstanceId) -> CloudRunnerInstance | None:
        """Get a self-hosted runner by instance id.

        Args:
            instance_id: The instance id.

        Returns:
            Information on the runner instance.
        """
        instance = self._openstack_cloud.get_instance(instance_id)
        healthy = self._runner_health_check(instance=instance)
        return (
            CloudRunnerInstance(
                name=instance.server_name,
                instance_id=instance_id,
                health=HealthState.HEALTHY if healthy else HealthState.UNHEALTHY,
                state=CloudRunnerState.from_openstack_server_status(instance.status),
            )
            if instance is not None
            else None
        )

    def get_runners(
        self, states: Sequence[CloudRunnerState] | None = None
    ) -> tuple[CloudRunnerInstance, ...]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.

        Returns:
            Information on the runner instances.
        """
        instance_list = self._openstack_cloud.get_instances()
        instance_list = [
            CloudRunnerInstance(
                name=instance.server_name,
                instance_id=instance.instance_id,
                health=(
                    HealthState.HEALTHY
                    if self._runner_health_check(instance)
                    else HealthState.UNHEALTHY
                ),
                state=CloudRunnerState.from_openstack_server_status(instance.status),
            )
            for instance in instance_list
        ]
        if states is None:
            return tuple(instance_list)
        return tuple(instance for instance in instance_list if instance.state in states)

    def delete_runner(
        self, instance_id: InstanceId, remove_token: str
    ) -> runner_metrics.RunnerMetrics | None:
        """Delete self-hosted runners.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.

        Returns:
            Any metrics collected during the deletion of the runner.
        """
        instance = self._openstack_cloud.get_instance(instance_id)
        if instance is None:
            logger.warning(
                "Unable to delete instance %s as it is not found",
                self._openstack_cloud.get_server_name(instance_id),
            )
            return None

        extracted_metrics = runner_metrics.extract(
            metrics_storage_manager=metrics_storage, runners=set([instance.server_name])
        )
        self._delete_runner(instance, remove_token)
        return next(extracted_metrics, None)

    def flush_runners(
        self, remove_token: str, busy: bool = False
    ) -> Iterator[runner_metrics.RunnerMetrics]:
        """Remove idle and/or busy runners.

        Args:
            remove_token:
            busy: If false, only idle runners are removed. If true, both idle and busy runners are
                removed.

        Returns:
            Any metrics retrieved from flushed runners.
        """
        instance_list = self._openstack_cloud.get_instances()
        for instance in instance_list:
            try:
                self._check_state_and_flush(instance, busy)
            except SSHError:
                logger.warning(
                    "Unable to determine state of  %s and kill runner process due to SSH issues",
                    instance.server_name,
                )
                continue
        return self.cleanup(remove_token)

    def cleanup(self, remove_token: str) -> Iterator[runner_metrics.RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Args:
            remove_token: The GitHub remove token.

        Returns:
            Any metrics retrieved from cleanup runners.
        """
        runners = self._get_runners_health()
        healthy_runner_names = [runner.server_name for runner in runners.healthy]
        metrics = runner_metrics.extract(
            metrics_storage_manager=metrics_storage, runners=set(healthy_runner_names)
        )
        for runner in runners.unhealthy:
            self._delete_runner(runner, remove_token)

        self._openstack_cloud.cleanup()
        return metrics

    def _delete_runner(self, instance: OpenstackInstance, remove_token: str) -> None:
        """Delete self-hosted runners by openstack instance.

        Args:
            instance: The OpenStack instance.
            remove_token: The GitHub remove token.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
            self._pull_runner_metrics(instance.server_name, ssh_conn)

            try:
                OpenstackRunnerManager._run_runner_removal_script(
                    instance.server_name, ssh_conn, remove_token
                )
            except GithubRunnerRemoveError:
                logger.warning(
                    "Unable to run github runner removal script for %s",
                    instance.server_name,
                    stack_info=True,
                )
        except SSHError:
            logger.exception(
                "Failed to get SSH connection while removing %s", instance.server_name
            )
            logger.warning(
                "Skipping runner remove script for %s due to SSH issues", instance.server_name
            )

        try:
            self._openstack_cloud.delete_instance(instance.instance_id)
        except OpenStackError:
            logger.exception(
                "Unable to delete openstack instance for runner %s", instance.server_name
            )

    def _get_runners_health(self) -> _RunnerHealth:
        """Get runners by health state.

        Returns:
            Runners by health state.
        """
        runner_list = self._openstack_cloud.get_instances()

        healthy, unhealthy = [], []
        for runner in runner_list:
            if self._runner_health_check(runner):
                healthy.append(runner)
            else:
                unhealthy.append(runner)
        return _RunnerHealth(healthy=tuple(healthy), unhealthy=tuple(unhealthy))

    def _runner_health_check(self, instance: OpenstackInstance) -> bool:
        """Run health check on a runner.

        Args:
            instance: The instance hosting the runner to run health check on.

        Returns:
            True if runner is healthy.
        """
        cloud_state = CloudRunnerState.from_openstack_server_status(instance.status)
        return cloud_state not in set(
            (
                CloudRunnerState.DELETED,
                CloudRunnerState.ERROR,
                CloudRunnerState.STOPPED,
            )
        ) and self._health_check(instance)

    def _generate_cloud_init(self, instance_name: str, registration_token: str) -> str:
        """Generate cloud init userdata.

        This is the script the openstack server runs on startup.

        Args:
            instance_name: The name of the instance.
            registration_token: The GitHub runner registration token.

        Returns:
            The cloud init userdata for openstack instance.
        """
        jinja = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)

        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(PRE_JOB_SCRIPT),
            dockerhub_mirror=self._service_config.dockerhub_mirror or "",
            ssh_debug_info=(
                secrets.choice(self._service_config.ssh_debug_connections)
                if self._service_config.ssh_debug_connections
                else None
            ),
        )

        pre_job_contents_dict = {
            "issue_metrics": True,
            "metrics_exchange_path": str(METRICS_EXCHANGE_PATH),
            "do_repo_policy_check": False,
        }
        repo_policy = self._get_repo_policy_compliance_client()
        if repo_policy is not None:
            pre_job_contents_dict.update(
                {
                    "repo_policy_base_url": repo_policy.base_url,
                    "repo_policy_one_time_token": repo_policy.get_one_time_token(),
                    "do_repo_policy_check": True,
                }
            )

        pre_job_contents = jinja.get_template("pre-job.j2").render(pre_job_contents_dict)

        runner_group = None
        if isinstance(self._runner_config.github_path, GithubOrg):
            runner_group = self._runner_config.github_path.group
        aproxy_address = (
            self._service_config.proxy_config.aproxy_address
            if self._service_config.proxy_config is not None
            else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            github_url=f"https://github.com/{self._runner_config.github_path.path()}",
            runner_group=runner_group,
            token=registration_token,
            instance_labels=",".join(self._runner_config.labels),
            instance_name=instance_name,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=self._service_config.dockerhub_mirror,
        )

    def _get_repo_policy_compliance_client(self) -> RepoPolicyComplianceClient | None:
        """Get repo policy compliance client.

        Returns:
            The repo policy compliance client.
        """
        if self._service_config.repo_policy_url and self._service_config.repo_policy_token:
            return RepoPolicyComplianceClient(
                self._service_config.repo_policy_url, self._service_config.repo_policy_token
            )
        return None

    @retry(tries=3, delay=5, backoff=2, local_logger=logger)
    def _check_state_and_flush(self, instance: OpenstackInstance, busy: bool) -> None:
        """Kill runner process depending on idle or busy.

        Due to update to runner state has some delay with GitHub API. The state of the runner is
        determined by which runner processes are running. If the Runner.Worker process is running,
        the runner is deemed to be busy.

        Raises:
            SSHError: Unable to check the state of the runner and kill the runner process due to
                SSH failure.

        Args:
            instance: The openstack instance to kill the runner process.
            busy: Kill the process if runner is busy, else only kill runner
                process if runner is idle.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except KeyfileError:
            logger.exception(
                "Health check failed due to unable to find keyfile for %s", instance.server_name
            )
            return
        except SSHError:
            logger.exception(
                "SSH connection failure with %s during health check", instance.server_name
            )
            raise

        # Using a single command to determine the state and kill the process if needed.
        # This makes it more robust when network is unstable.
        if busy:
            logger.info("Attempting to kill all runner process on %s", instance.server_name)
            # kill both Runner.Listener and Runner.Worker processes.
            # This kills pre-job.sh, a child process of Runner.Worker.
            kill_command = (
                f"pgrep -x {RUNNER_LISTENER_PROCESS} && kill $(pgrep -x {RUNNER_LISTENER_PROCESS});"
                f"pgrep -x {RUNNER_WORKER_PROCESS} && kill $(pgrep -x {RUNNER_WORKER_PROCESS});"
            )
        else:
            logger.info(
                "Attempting to kill runner process on %s if not busy", instance.server_name
            )
            # Only kill Runner.Listener if Runner.Worker does not exist.
            kill_command = (
                f"pgrep -x {RUNNER_WORKER_PROCESS} || pgrep -x {RUNNER_LISTENER_PROCESS} && "
                f"kill $(pgrep -x {RUNNER_LISTENER_PROCESS})"
            )
        # Checking the result of kill command is not useful, as the exit code does not reveal much.
        ssh_conn.run(kill_command, warn=True)
        
        # TODO: debug
        result = ssh_conn.run("ps aux", warn=True)
        import pytest
        pytest.set_trace()

        result = ssh_conn.run("ps aux", warn=True)
        import pytest
        pytest.set_trace()

    @retry(tries=3, delay=5, backoff=2, local_logger=logger)
    def _health_check(self, instance: OpenstackInstance) -> bool:
        """Check whether runner is healthy.

        Args:
            instance: The OpenStack instance to conduit the health check.

        Raises:
            SSHError: Unable to get a SSH connection to the instance.

        Returns:
            Whether the runner is healthy.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except KeyfileError:
            logger.exception(
                "Health check failed due to unable to find keyfile for %s", instance.server_name
            )
            return False
        except SSHError:
            logger.exception(
                "SSH connection failure with %s during health check", instance.server_name
            )
            raise
        return OpenstackRunnerManager._run_health_check(ssh_conn, instance.server_name)

    @staticmethod
    def _run_health_check(ssh_conn: SSHConnection, name: str) -> bool:
        """Run a health check for runner process.

        Args:
            ssh_conn: The SSH connection to the runner.
            name: The name of the runner.

        Returns:
            Whether the health succeed.
        """
        result: invoke.runners.Result = ssh_conn.run("ps aux", warn=True)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s: %s", name, result.stderr)
            return False
        if (
            RUNNER_WORKER_PROCESS not in result.stdout
            and RUNNER_LISTENER_PROCESS not in result.stdout
        ):
            logger.warning("Runner process not found on %s", name)
            return False
        return True

    @retry(tries=10, delay=60, local_logger=logger)
    def _wait_runner_startup(self, instance: OpenstackInstance) -> None:
        """Wait until runner is startup.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner startup process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH to {instance.server_name} during creation possible due to setup "
                "not completed"
            ) from err

        result: invoke.runners.Result = ssh_conn.run("ps aux", warn=True)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s", instance.server_name)
            raise RunnerStartError(f"Unable to SSH run `ps aux` on {instance.server_name}")
        if RUNNER_STARTUP_PROCESS not in result.stdout:
            logger.warning("Runner startup process not found on %s", instance.server_name)
            raise RunnerStartError(f"Runner startup process not found on {instance.server_name}")
        logger.info("Runner startup process found to be healthy on %s", instance.server_name)

    @retry(tries=5, delay=60, local_logger=logger)
    def _wait_runner_running(self, instance: OpenstackInstance) -> None:
        """Wait until runner is running.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH connect to {instance.server_name} openstack runner"
            ) from err

        if not self._run_health_check(ssh_conn=ssh_conn, name=instance.server_name):
            logger.info("Runner process not found on %s", instance.server_name)
            raise RunnerStartError(
                f"Runner process on {instance.server_name} failed to initialize on after starting"
            )

        logger.info("Runner process found to be healthy on %s", instance.server_name)

    @staticmethod
    def _generate_instance_id() -> InstanceId:
        """Generate a instance id.

        Return:
            The id.
        """
        return secrets.token_hex(12)

    @staticmethod
    def _issue_runner_installed_metric(
        name: str,
        flavor: str,
        install_start_timestamp: float,
        install_end_timestamp: float,
    ) -> None:
        """Issue metric for runner installed event.

        Args:
            name: The name of the runner.
            flavor: The flavor of the runner.
            install_start_timestamp: The timestamp of installation start.
            install_end_timestamp: The timestamp of installation end.
        """
        try:
            metric_events.issue_event(
                event=metric_events.RunnerInstalled(
                    timestamp=install_start_timestamp,
                    flavor=flavor,
                    duration=install_end_timestamp - install_start_timestamp,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue RunnerInstalled metric")

        try:
            storage = metrics_storage.create(name)
        except CreateMetricsStorageError:
            logger.exception(
                "Failed to create metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
        else:
            try:
                (storage.path / runner_metrics.RUNNER_INSTALLED_TS_FILE_NAME).write_text(
                    str(install_end_timestamp), encoding="utf-8"
                )
            except FileNotFoundError:
                logger.exception(
                    "Failed to write runner-installed.timestamp into metrics storage "
                    "for runner %s, will not be able to issue all metrics.",
                    name,
                )

    @staticmethod
    def _pull_runner_metrics(name: str, ssh_conn: SSHConnection) -> None:
        """Pull metrics from runner.

        Args:
            name: The name of the runner.
            ssh_conn: The SSH connection to the runner.
        """
        try:
            storage = metrics_storage.get(name)
        except GetMetricsStorageError:
            logger.exception(
                "Failed to get shared metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
            return

        try:
            OpenstackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "pre-job-metrics.json"),
                local_path=str(storage.path / "pre-job-metrics.json"),
                max_size=MAX_METRICS_FILE_SIZE,
            )
            OpenstackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "post-job-metrics.json"),
                local_path=str(storage.path / "post-job-metrics.json"),
                max_size=MAX_METRICS_FILE_SIZE,
            )
        except _PullFileError as exc:
            logger.warning(
                "Failed to pull metrics for %s: %s . Will not be able to issue all metrics",
                name,
                exc,
            )

    @staticmethod
    def _ssh_pull_file(
        ssh_conn: SSHConnection, remote_path: str, local_path: str, max_size: int
    ) -> None:
        """Pull file from the runner instance.

        Args:
            ssh_conn: The SSH connection instance.
            remote_path: The file path on the runner instance.
            local_path: The local path to store the file.
            max_size: If the file is larger than this, it will not be pulled.

        Raises:
            _PullFileError: Unable to pull the file from the runner instance.
            SSHError: Issue with SSH connection.
        """
        try:
            result = ssh_conn.run(f"stat -c %s {remote_path}", warn=True)
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
        if not result.ok:
            logger.warning(
                (
                    "Unable to get file size of %s on instance %s, "
                    "exit code: %s, stdout: %s, stderr: %s"
                ),
                remote_path,
                ssh_conn.host,
                result.return_code,
                result.stdout,
                result.stderr,
            )
            raise _PullFileError(f"Unable to get file size of {remote_path}")

        stdout = result.stdout
        try:
            stdout.strip()
            size = int(stdout)
            if size > max_size:
                raise _PullFileError(f"File size of {remote_path} too large {size} > {max_size}")
        except ValueError as exc:
            raise _PullFileError(f"Invalid file size for {remote_path}: stdout") from exc

        try:
            ssh_conn.get(remote=remote_path, local=local_path)
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
        except OSError as exc:
            raise _PullFileError(f"Unable to retrieve file {remote_path}") from exc

    @staticmethod
    def _run_runner_removal_script(
        instance_name: str, ssh_conn: SSHConnection, remove_token: str
    ) -> None:
        """Run Github runner removal script.

        Args:
            instance_name: The name of the runner instance.
            ssh_conn: The SSH connection to the runner instance.
            remove_token: The GitHub instance removal token.

        Raises:
            GithubRunnerRemoveError: Unable to remove runner from GitHub.
        """
        try:
            result = ssh_conn.run(
                f"{_CONFIG_SCRIPT_PATH} remove --token {remove_token}",
                warn=True,
            )
            if result.ok:
                return

            logger.warning(
                (
                    "Unable to run removal script on instance %s, "
                    "exit code: %s, stdout: %s, stderr: %s"
                ),
                instance_name,
                result.return_code,
                result.stdout,
                result.stderr,
            )
            raise GithubRunnerRemoveError(f"Failed to remove runner {instance_name} from Github.")
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise GithubRunnerRemoveError(
                f"Failed to remove runner {instance_name} from Github."
            ) from exc
