# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import logging
import pathlib
import time
from datetime import datetime, timezone
from functools import partial
from typing import TYPE_CHECKING, Callable, Generator, TypeVar, cast

import github
import jubilant
import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowJob import WorkflowJob
from github.WorkflowRun import WorkflowRun
from github_runner_manager.metrics.events import get_metrics_log_path

from charm import UPGRADE_MSG
from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    GITHUB_APP_CLIENT_ID_CONFIG_NAME,
    GITHUB_APP_INSTALLATION_ID_CONFIG_NAME,
    GITHUB_APP_PRIVATE_KEY_SECRET_ID_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_SECRET_ID_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TEST_MODE_CONFIG_NAME,
    TOKEN_SECRET_ID_CONFIG_NAME,
)
from manager_service import _get_log_file_path

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME = "workflow_dispatch_failure_test.yaml"
DISPATCH_WAIT_TEST_WORKFLOW_FILENAME = "workflow_dispatch_wait_test.yaml"
DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME = "e2e_test_run.yaml"
DISPATCH_E2E_TEST_RUN_OPENSTACK_WORKFLOW_FILENAME = "e2e_test_run_openstack.yaml"

# 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
# https://github.com/canonical/snapd/pull/16131
DEFAULT_RUNNER_CONSTRAINTS = {
    "root-disk": "20480M",
    "virt-type": "virtual-machine",
}

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tests.integration.conftest import GitHubConfig, ProxyConfig


def run_in_unit(
    juju: jubilant.Juju,
    unit_name: str,
    command: str,
    timeout: float | None = None,
    assert_on_failure: bool = False,
    assert_msg: str = "",
) -> tuple[int, str, str]:
    """Run command in juju unit.

    Args:
        juju: Jubilant Juju instance.
        unit_name: Name of the unit (e.g. "app/0").
        command: Command to execute.
        timeout: Amount of time to wait for the execution.
        assert_on_failure: Whether to assert on command failure.
        assert_msg: Message to include in the assertion.

    Returns:
        Tuple of return code, stdout and stderr.
    """
    try:
        task = juju.exec(command, unit=unit_name, wait=timeout)
        code, stdout, stderr = task.return_code, task.stdout, task.stderr
    except jubilant.TaskError as e:
        code, stdout, stderr = e.task.return_code, e.task.stdout, e.task.stderr

    if assert_on_failure:
        assert code == 0, f"{assert_msg}: {stderr}"

    return code, stdout, stderr


def wait_for_runner_ready(juju: jubilant.Juju, app_name: str, num_runners: int = 1) -> None:
    """Wait until the expected number of runners are online.

    Args:
        juju: Jubilant Juju instance.
        app_name: The GitHub Runner Charm application name.
        num_runners: The minimum number of runners expected online.
    """
    unit_name = f"{app_name}/0"
    for attempt in range(20):
        try:
            result = juju.run(unit_name, "check-runners")
        except (jubilant.CLIError, TimeoutError):
            logger.info("check-runners failed (attempt %d), retrying...", attempt)
            time.sleep(30)
            continue

        if result.status == "completed" and int(result.results["online"]) >= num_runners:
            break

        time.sleep(30)
    else:
        assert False, f"Timeout waiting for {num_runners} runner(s) to be ready"


def deploy_github_runner_charm(
    juju: jubilant.Juju,
    charm_file: str,
    app_name: str,
    github_config: "GitHubConfig",
    proxy_config: "ProxyConfig",
    reconcile_interval: int,
    openstack_clouds_yaml: str | None = None,
    constraints: dict | None = None,
    config: dict | None = None,
    deploy_kwargs: dict | None = None,
    wait_idle: bool = True,
    base: str = "ubuntu@22.04",
) -> str:
    """Deploy github-runner charm.

    Args:
        juju: Jubilant Juju instance.
        charm_file: Path of the charm file to deploy.
        app_name: Application name for the deployment.
        github_config: Object providing GitHub settings with attributes `path` and `token`.
        proxy_config: Object providing proxy settings with attributes `http_proxy`,
            `https_proxy`, and `no_proxy`.
        reconcile_interval: Time between reconcile for the application.
        openstack_clouds_yaml: Plaintext OpenStack clouds.yaml to wrap in a Juju secret.
        constraints: The custom machine constraints to use. See DEFAULT_RUNNER_CONSTRAINTS
            otherwise.
        config: Additional custom config to use.
        deploy_kwargs: Additional model deploy arguments.
        wait_idle: wait for model to become idle.
        base: Charm base to deploy on (e.g., ubuntu@22.04).

    Returns:
        The application name that was deployed.
    """
    juju.model_config(
        values={
            "juju-http-proxy": proxy_config.http_proxy,
            "juju-https-proxy": proxy_config.https_proxy,
            "juju-no-proxy": proxy_config.no_proxy,
            "logging-config": "<root>=INFO;unit=INFO",
        }
    )

    default_config: dict[str, str | int | bool] = {
        PATH_CONFIG_NAME: github_config.path,
        BASE_VIRTUAL_MACHINES_CONFIG_NAME: 0,
        TEST_MODE_CONFIG_NAME: "insecure",
        RECONCILE_INTERVAL_CONFIG_NAME: reconcile_interval,
    }

    secret_names: list[str] = []
    if github_config.has_app_auth:
        assert github_config.app_client_id is not None
        assert github_config.installation_id is not None
        assert github_config.private_key is not None
        secret_name = f"{app_name}-gh-app-key"
        secret_id = juju.add_secret(
            name=secret_name,
            content={"private-key": github_config.private_key},
        )
        secret_names.append(secret_name)
        default_config[GITHUB_APP_CLIENT_ID_CONFIG_NAME] = github_config.app_client_id
        default_config[GITHUB_APP_INSTALLATION_ID_CONFIG_NAME] = github_config.installation_id
        default_config[GITHUB_APP_PRIVATE_KEY_SECRET_ID_CONFIG_NAME] = str(secret_id)
    else:
        token_secret_name = f"{app_name}-github-token"
        token_secret_id = juju.add_secret(
            name=token_secret_name,
            content={"github-token": github_config.token},
        )
        secret_names.append(token_secret_name)
        default_config[TOKEN_SECRET_ID_CONFIG_NAME] = str(token_secret_id)

    if openstack_clouds_yaml:
        openstack_secret_name = f"{app_name}-openstack-clouds"
        openstack_secret_id = juju.add_secret(
            name=openstack_secret_name,
            content={"clouds-yaml": openstack_clouds_yaml},
        )
        secret_names.append(openstack_secret_name)
        default_config[OPENSTACK_CLOUDS_YAML_SECRET_ID_CONFIG_NAME] = str(openstack_secret_id)

    if config:
        default_config.update(config)

    juju.deploy(
        charm_file,
        app=app_name,
        base=base,
        config=default_config,
        constraints=constraints or DEFAULT_RUNNER_CONSTRAINTS,
        **(deploy_kwargs or {}),
    )

    for secret_name in secret_names:
        juju.grant_secret(secret_name, app_name)

    if wait_idle:
        juju.wait(
            lambda status: jubilant.all_active(status, app_name),
            timeout=60 * 20,
        )

    return app_name


def get_job_logs(job: WorkflowJob) -> str:
    """Retrieve a workflow's job logs.

    Args:
        job: The target job to fetch the logs from.

    Returns:
        The job logs.
    """
    logs_url = job.logs_url()
    logs = requests.get(logs_url).content.decode("utf-8")
    return logs


def get_workflow_runs(
    start_time: datetime,
    workflow: Workflow,
    runner_name: str,
    branch: Branch | None = None,
) -> Generator[WorkflowRun, None, None]:
    """Fetch the latest matching runs of a workflow for a given runner.

    Args:
        start_time: The start time of the workflow.
        workflow: The target workflow to get the run for.
        runner_name: The runner name the workflow job is assigned to.
        branch: The branch the workflow is run on.

    Yields:
        The workflow run.
    """
    for run in workflow.get_runs(
        created=f">={start_time.isoformat()}", branch=branch or github.GithubObject.NotSet
    ):
        latest_job: WorkflowJob = run.jobs()[0]
        logs = get_job_logs(job=latest_job)

        if runner_name in logs:
            yield run


def _get_latest_run(
    workflow: Workflow, start_time: datetime, branch: Branch | None = None
) -> WorkflowRun | None:
    """Get the latest run after start_time.

    Args:
        workflow: The workflow to get the latest run for.
        start_time: The minimum start time of the run.
        branch: The branch in which the workflow belongs to.

    Returns:
        The latest workflow run if the workflow has started. None otherwise.
    """
    try:
        return workflow.get_runs(
            branch=branch or github.GithubObject.NotSet,
            created=f">={start_time.isoformat(timespec='seconds')}",
        )[0]
    except IndexError:
        return None


def _is_workflow_run_complete(run: WorkflowRun) -> bool:
    """Wait for the workflow status to turn to complete.

    Args:
        run: The workflow run to check status for.

    Returns:
        Whether the run status is "completed".

    """
    return _has_workflow_run_status(run=run, status="completed")


def _has_workflow_run_status(run: WorkflowRun, status: str) -> bool:
    """Check if the workflow run has a specific status.

    Args:
        run: The workflow run to check status for.
        status: The status to check for.

    Returns:
        Whether the run status is the expected status.
    """
    if run.update():
        return run.status == status
    return False


def dispatch_workflow(
    app_name: str | None,
    branch: Branch,
    github_repository: Repository,
    conclusion: str,
    workflow_id_or_name: str,
    dispatch_input: dict | None = None,
    wait: bool = True,
) -> WorkflowRun:
    """Dispatch a workflow on a branch for the runner to run.

    The function assumes that there is only one runner running in the unit.

    Args:
        app_name: The charm application name to dispatch the workflow for.
        branch: The branch to dispatch the workflow on.
        github_repository: The github repository to dispatch the workflow on.
        conclusion: The expected workflow run conclusion.
            This argument is ignored if wait is False.
        workflow_id_or_name: The workflow filename in .github/workflows in main branch to run or
            its id.
        dispatch_input: Workflow input values.
        wait: Whether to wait for runner to run workflow until completion.

    Returns:
        The workflow run.
    """
    if dispatch_input is None:
        assert app_name is not None, "If dispatch input not given the app_name cannot be None."
        dispatch_input = {"runner": app_name}

    start_time = datetime.now(timezone.utc)

    workflow = github_repository.get_workflow(id_or_file_name=workflow_id_or_name)

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, dispatch_input), "Failed to create workflow"

    # There is a very small chance of selecting a run not created by the dispatch above.
    run: WorkflowRun | None = wait_for(
        partial(_get_latest_run, workflow=workflow, start_time=start_time, branch=branch),
        timeout=10 * 60,
    )
    assert run, f"Run not found for workflow: {workflow.name} ({workflow.id})"

    if not wait:
        return run
    wait_for_completion(run=run, conclusion=conclusion)

    return run


def wait_for_status(run: WorkflowRun, status: str) -> None:
    """Wait for the workflow run to start.

    Args:
        run: The workflow run to wait for.
        status: The expected status of the run.
    """
    wait_for(
        partial(_has_workflow_run_status, run=run, status=status),
        timeout=60 * 5,
        check_interval=10,
    )


def wait_for_completion(run: WorkflowRun, conclusion: str) -> None:
    """Wait for the workflow run to complete.

    Args:
        run: The workflow run to wait for.
        conclusion: The expected conclusion of the run.
    """
    wait_for(
        partial(_is_workflow_run_complete, run=run),
        timeout=60 * 30,
        check_interval=60,
    )
    # The run object is updated by _is_workflow_run_complete function above.
    assert (
        run.conclusion == conclusion
    ), f"Unexpected run conclusion, expected: {conclusion}, got: {run.conclusion}"


R = TypeVar("R")


def wait_for(
    func: Callable[[], R],
    timeout: int | float = 300,
    check_interval: int = 10,
) -> R:
    """Wait for function execution to become truthy.

    Args:
        func: A callback function to wait to return a truthy value.
        timeout: Time in seconds to wait for function result to become truthy.
        check_interval: Time in seconds to wait between ready checks.

    Raises:
        TimeoutError: if the callback function did not return a truthy value within timeout.

    Returns:
        The result of the function if any.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = func()
        if cast(bool, result):
            return result
        logger.info("Wait for condition not met, sleeping %s", check_interval)
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    result = func()
    if cast(bool, result):
        return result
    raise TimeoutError()


def is_upgrade_charm_event_emitted(juju: jubilant.Juju, unit_name: str) -> bool:
    """Check if the upgrade_charm event is emitted.

    This is to ensure false positives from only waiting for ACTIVE status.

    Args:
        juju: Jubilant Juju instance.
        unit_name: The unit name to check for upgrade charm event.

    Returns:
        bool: True if the event is emitted, False otherwise.
    """
    unit_name_without_slash = unit_name.replace("/", "-")
    juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
    ret_code, stdout, stderr = run_in_unit(
        juju=juju, unit_name=unit_name, command=f"cat {juju_unit_log_file} | grep '{UPGRADE_MSG}'"
    )
    assert ret_code == 0, f"Failed to read the log file: {stderr}"
    return stdout is not None and UPGRADE_MSG in stdout


def get_file_content(juju: jubilant.Juju, unit_name: str, filepath: pathlib.Path) -> str:
    """Retrieve the file content in the unit.

    Args:
        juju: Jubilant Juju instance.
        unit_name: The unit name to retrieve the file content from.
        filepath: The path of the file to retrieve.

    Returns:
        The file content
    """
    retcode, stdout, stderr = run_in_unit(
        juju=juju,
        unit_name=unit_name,
        command=f"if [ -f {filepath} ]; then cat {filepath}; else echo ''; fi",
    )
    assert retcode == 0, f"Failed to get content of {filepath}: {stdout} {stderr}"
    assert stdout, f"Failed to get content of {filepath}, no stdout message"
    logging.info("File content of %s: %s", filepath, stdout)
    return stdout.strip()


def get_github_runner_manager_service_log(juju: jubilant.Juju, unit_name: str) -> str:
    """Get the logs of github-runner-manager service.

    Args:
        juju: Jubilant Juju instance.
        unit_name: The unit name to get the logs from.

    Returns:
        The logs.
    """
    log_file_path = _get_log_file_path(unit_name)
    return_code, stdout, stderr = run_in_unit(
        juju,
        unit_name,
        f"cat {log_file_path}",
        timeout=60,
        assert_on_failure=True,
        assert_msg="Failed to get the GitHub runner manager logs",
    )

    assert return_code == 0, f"Get log with cat {log_file_path} failed with: {stderr}"
    assert stdout
    return stdout


def get_github_runner_metrics_log(juju: jubilant.Juju, unit_name: str) -> str:
    """Get the github-runner-manager metric logs.

    Args:
        juju: Jubilant Juju instance.
        unit_name: The unit name to get the logs from.

    Returns:
        Runner metrics logs.
    """
    log_file_path = get_metrics_log_path()
    _, stdout, stderr = run_in_unit(
        juju,
        unit_name,
        f"cat {log_file_path}",
        timeout=60,
        assert_on_failure=False,
        assert_msg="Failed to get the GitHub runner manager metrics",
    )

    return stdout or stderr or "Empty metrics log"
