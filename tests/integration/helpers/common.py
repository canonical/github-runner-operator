# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import inspect
import logging
import pathlib
import time
import typing
from datetime import datetime, timezone
from functools import partial
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

import github
import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowJob import WorkflowJob
from github.WorkflowRun import WorkflowRun
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from charm import UPGRADE_MSG
from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TEST_MODE_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
)
from tests.status_name import ACTIVE

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME = "workflow_dispatch_failure_test.yaml"
DISPATCH_WAIT_TEST_WORKFLOW_FILENAME = "workflow_dispatch_wait_test.yaml"
DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME = "e2e_test_run.yaml"
DISPATCH_E2E_TEST_RUN_OPENSTACK_WORKFLOW_FILENAME = "e2e_test_run_openstack.yaml"

MONGODB_APP_NAME = "mongodb"
DEFAULT_RUNNER_CONSTRAINTS = {"root-disk": 15}

logger = logging.getLogger(__name__)


async def run_in_unit(
    unit: Unit, command: str, timeout=None, assert_on_failure=False, assert_msg=""
) -> tuple[int, str | None, str | None]:
    """Run command in juju unit.

    Args:
        unit: Juju unit to execute the command in.
        command: Command to execute.
        timeout: Amount of time to wait for the execution.
        assert_on_failure: Whether to assert on command failure.
        assert_msg: Message to include in the assertion.

    Returns:
        Tuple of return code, stdout and stderr.
    """
    action: Action = await unit.run(command, timeout)

    await action.wait()
    code, stdout, stderr = (
        action.results["return-code"],
        action.results.get("stdout", None),
        action.results.get("stderr", None),
    )

    if assert_on_failure:
        assert code == 0, f"{assert_msg}: {stderr}"

    return code, stdout, stderr


async def reconcile(app: Application, model: Model) -> None:
    """Reconcile the runners.

    Uses the first unit found in the application for the reconciliation.

    Args:
        app: The GitHub Runner Charm app to reconcile the runners for.
        model: The machine charm model.
    """
    action = await app.units[0].run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(apps=[app.name], status=ACTIVE)


async def deploy_github_runner_charm(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
    reconcile_interval: int,
    constraints: dict | None = None,
    config: dict | None = None,
    deploy_kwargs: dict | None = None,
    wait_idle: bool = True,
) -> Application:
    """Deploy github-runner charm.

    Args:
        model: Model to deploy the charm.
        charm_file: Path of the charm file to deploy.
        app_name: Application name for the deployment.
        path: Path representing the GitHub repo/org.
        token: GitHub Personal Token for the application to use.
        http_proxy: HTTP proxy for the application to use.
        https_proxy: HTTPS proxy for the application to use.
        no_proxy: No proxy configuration for the application.
        reconcile_interval: Time between reconcile for the application.
        constraints: The custom machine constraints to use. See DEFAULT_RUNNER_CONSTRAINTS
            otherwise.
        config: Additional custom config to use.
        deploy_kwargs: Additional model deploy arguments.
        wait_idle: wait for model to become idle.

    Returns:
        The charm application that was deployed.
    """
    await model.set_config(
        {
            "juju-http-proxy": http_proxy,
            "juju-https-proxy": https_proxy,
            "juju-no-proxy": no_proxy,
            "logging-config": "<root>=INFO;unit=INFO",
        }
    )

    default_config = {
        PATH_CONFIG_NAME: path,
        TOKEN_CONFIG_NAME: token,
        BASE_VIRTUAL_MACHINES_CONFIG_NAME: 0,
        TEST_MODE_CONFIG_NAME: "insecure",
        RECONCILE_INTERVAL_CONFIG_NAME: reconcile_interval,
    }

    if config:
        default_config.update(config)

    application = await model.deploy(
        charm_file,
        application_name=app_name,
        base="ubuntu@22.04",
        config=default_config,
        constraints=constraints or DEFAULT_RUNNER_CONSTRAINTS,
        **(deploy_kwargs or {}),
    )

    if wait_idle:
        await model.wait_for_idle(status=ACTIVE, timeout=60 * 20)

    return application


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
    start_time: datetime, workflow: Workflow, runner_name: str, branch: Branch = None
) -> typing.Generator[WorkflowRun, None, None]:
    """Fetch the latest matching runs of a workflow for a given runner.

    Args:
        start_time: The start time of the workflow.
        workflow: The target workflow to get the run for.
        runner_name: The runner name the workflow job is assigned to.
        branch: The branch the workflow is run on.

    Yields:
        The workflow run.
    """
    if branch is None:
        branch = github.GithubObject.NotSet

    for run in workflow.get_runs(created=f">={start_time.isoformat()}", branch=branch):
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
            branch=branch, created=f">={start_time.isoformat(timespec='seconds')}"
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


async def dispatch_workflow(
    app: Application | None,
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
        app: The charm to dispatch the workflow for.
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
        assert app is not None, "If dispatch input not given the app cannot be None."
        dispatch_input = {"runner": app.name}

    start_time = datetime.now(timezone.utc)

    workflow = github_repository.get_workflow(id_or_file_name=workflow_id_or_name)

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, dispatch_input), "Failed to create workflow"

    # There is a very small chance of selecting a run not created by the dispatch above.
    run: WorkflowRun | None = await wait_for(
        partial(_get_latest_run, workflow=workflow, start_time=start_time, branch=branch),
        timeout=10 * 60,
    )
    assert run, f"Run not found for workflow: {workflow.name} ({workflow.id})"

    if not wait:
        return run
    await wait_for_completion(run=run, conclusion=conclusion)

    return run


async def wait_for_status(run: WorkflowRun, status: str) -> None:
    """Wait for the workflow run to start.

    Args:
        run: The workflow run to wait for.
        status: The expected status of the run.
    """
    await wait_for(
        partial(_has_workflow_run_status, run=run, status=status),
        timeout=60 * 5,
        check_interval=10,
    )


async def wait_for_completion(run: WorkflowRun, conclusion: str) -> None:
    """Wait for the workflow run to complete.

    Args:
        run: The workflow run to wait for.
        conclusion: The expected conclusion of the run.
    """
    await wait_for(
        partial(_is_workflow_run_complete, run=run),
        timeout=60 * 30,
        check_interval=60,
    )
    # The run object is updated by _is_workflow_run_complete function above.
    assert (
        run.conclusion == conclusion
    ), f"Unexpected run conclusion, expected: {conclusion}, got: {run.conclusion}"


P = ParamSpec("P")
R = TypeVar("R")
S = Callable[P, R] | Callable[P, Awaitable[R]]


async def wait_for(
    func: S,
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
    is_awaitable = inspect.iscoroutinefunction(func)
    while time.time() < deadline:
        if is_awaitable:
            if result := await cast(Awaitable, func()):
                return result
        else:
            if result := func():
                return cast(R, result)
        logger.info("Wait for condition not met, sleeping %s", check_interval)
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if is_awaitable:
        if result := await cast(Awaitable, func()):
            return result
    else:
        if result := func():
            return cast(R, result)
    raise TimeoutError()


async def is_upgrade_charm_event_emitted(unit: Unit) -> bool:
    """Check if the upgrade_charm event is emitted.

    This is to ensure false positives from only waiting for ACTIVE status.

    Args:
        unit: The unit to check for upgrade charm event.

    Returns:
        bool: True if the event is emitted, False otherwise.
    """
    unit_name_without_slash = unit.name.replace("/", "-")
    juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
    ret_code, stdout, stderr = await run_in_unit(
        unit=unit, command=f"cat {juju_unit_log_file} | grep '{UPGRADE_MSG}'"
    )
    assert ret_code == 0, f"Failed to read the log file: {stderr}"
    return stdout is not None and UPGRADE_MSG in stdout


async def get_file_content(unit: Unit, filepath: pathlib.Path) -> str:
    """Retrieve the file content in the unit.

    Args:
        unit: The unit to retrieve the file content from.
        filepath: The path of the file to retrieve.

    Returns:
        The file content
    """
    retcode, stdout, stderr = await run_in_unit(
        unit=unit,
        command=f"if [ -f {filepath} ]; then cat {filepath}; else echo ''; fi",
    )
    assert retcode == 0, f"Failed to get content of {filepath}: {stdout} {stderr}"
    assert stdout is not None, f"Failed to get content of {filepath}, no stdout message"
    logging.info("File content of %s: %s", filepath, stdout)
    return stdout.strip()
