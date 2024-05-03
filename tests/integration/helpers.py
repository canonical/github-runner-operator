# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import inspect
import json
import logging
import subprocess
import time
import typing
from asyncio import sleep
from datetime import datetime, timezone
from functools import partial
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar, cast

import github
import juju.version
import requests
import yaml
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowJob import WorkflowJob
from github.WorkflowRun import WorkflowRun
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from charm_state import (
    DENYLIST_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    RUNNER_STORAGE_CONFIG_NAME,
    TEST_MODE_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
)
from runner import Runner
from runner_manager import RunnerManager
from tests.status_name import ACTIVE

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME = "workflow_dispatch_failure_test.yaml"
DISPATCH_WAIT_TEST_WORKFLOW_FILENAME = "workflow_dispatch_wait_test.yaml"
DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME = "e2e_test_run.yaml"

DEFAULT_RUNNER_CONSTRAINTS = {"root-disk": 15}

logger = logging.getLogger(__name__)


async def check_runner_binary_exists(unit: Unit) -> bool:
    """Checks if runner binary exists in the charm.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        Whether the runner binary file exists in the charm.
    """
    return_code, _, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    return return_code == 0


async def get_repo_policy_compliance_pip_info(unit: Unit) -> None | str:
    """Get pip info for repo-policy-compliance.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        If repo-policy-compliance is installed, returns the pip show output, else returns none.
    """
    return_code, stdout, stderr = await run_in_unit(
        unit, "python3 -m pip show repo-policy-compliance"
    )

    if return_code == 0:
        return stdout or stderr

    return None


async def install_repo_policy_compliance_from_git_source(unit: Unit, source: None | str) -> None:
    """Install repo-policy-compliance pip package from the git source.

    Args:
        unit: Unit instance to check for the LXD profile.
        source: The git source to install the package. If none the package is removed.
    """
    return_code, stdout, stderr = await run_in_unit(
        unit, "python3 -m pip uninstall --yes repo-policy-compliance"
    )
    assert return_code == 0, f"Failed to uninstall repo-policy-compliance: {stdout} {stderr}"

    if source:
        return_code, stdout, stderr = await run_in_unit(unit, f"python3 -m pip install {source}")
        assert (
            return_code == 0
        ), f"Failed to install repo-policy-compliance from source, {stdout} {stderr}"


async def remove_runner_bin(unit: Unit) -> None:
    """Remove runner binary.

    Args:
        unit: Unit instance to check for the LXD profile.
    """
    await run_in_unit(unit, f"rm {RunnerManager.runner_bin_path}")

    # No file should exists under with the filename.
    return_code, _, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    assert return_code != 0


async def assert_resource_lxd_profile(unit: Unit, configs: dict[str, Any]) -> None:
    """Check for LXD profile of the matching resource config.

    Args:
        unit: Unit instance to check for the LXD profile.
        configs: Configs of the application.
    """
    cpu = configs["vm-cpu"]["value"]
    mem = configs["vm-memory"]["value"]
    disk = configs["vm-disk"]["value"]
    resource_profile_name = Runner._get_resource_profile_name(cpu, mem, disk)

    # Verify the profile exists.
    return_code, stdout, _ = await run_in_unit(unit, "lxc profile list --format json")
    assert return_code == 0
    assert stdout is not None
    profiles = json.loads(stdout)
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    return_code, stdout, _ = await run_in_unit(unit, f"lxc profile show {resource_profile_name}")
    assert return_code == 0
    assert stdout is not None
    profile_content = yaml.safe_load(stdout)
    assert f"{cpu}" == profile_content["config"]["limits.cpu"]
    assert mem == profile_content["config"]["limits.memory"]
    assert disk == profile_content["devices"]["root"]["size"]


async def get_runner_names(unit: Unit) -> tuple[str, ...]:
    """Get names of the runners in LXD.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        Tuple of runner names.
    """
    return_code, stdout, _ = await run_in_unit(unit, "lxc list --format json")

    assert return_code == 0
    assert stdout is not None

    lxc_instance: list[dict[str, str]] = json.loads(stdout)
    return tuple(runner["name"] for runner in lxc_instance if runner["name"] != "builder")


async def wait_till_num_of_runners(unit: Unit, num: int, timeout: int = 10 * 60) -> None:
    """Wait and check the number of runners.

    Args:
        unit: Unit instance to check for the LXD profile.
        num: Number of runner instances to check for.
        timeout: Number of seconds to wait for the runners.
    """

    async def get_lxc_instances() -> None | list[dict]:
        """Get lxc instances list info.

        Returns:
            List of lxc instance dictionaries, None if failed to get list.
        """
        return_code, stdout, _ = await run_in_unit(unit, "lxc list --format json")
        if return_code != 0 or not stdout:
            logger.error("Failed to run lxc list, %s", return_code)
            return None
        return json.loads(stdout)

    async def is_desired_num_runners():
        """Return whether there are desired number of lxc instances running.

        Returns:
            Whether the desired number of lxc runners have been reached.
        """
        lxc_instances = await get_lxc_instances()
        if lxc_instances is None:
            return False
        return len(lxc_instances) == num

    await wait_for(is_desired_num_runners, timeout=timeout, check_interval=30)

    instances = await get_lxc_instances()
    if not instances:
        return

    for instance in instances:
        return_code, stdout, _ = await run_in_unit(unit, f"lxc exec {instance['name']} -- ps aux")
        assert return_code == 0

        assert stdout is not None
        assert f"/bin/bash {Runner.runner_script}" in stdout


def on_juju_2() -> bool:
    """Check if juju 2 is used.

    Returns:
        Whether juju 2 is used.
    """
    # The juju library does not support `__version__`.
    # Prior to juju 3, the SUPPORTED_MAJOR_VERSION was not defined.
    return not hasattr(juju.version, "SUPPORTED_MAJOR_VERSION")


async def run_in_unit(
    unit: Unit, command: str, timeout=None
) -> tuple[int, str | None, str | None]:
    """Run command in juju unit.

    Compatible with juju 3 and juju 2.

    Args:
        unit: Juju unit to execute the command in.
        command: Command to execute.
        timeout: Amount of time to wait for the execution.

    Returns:
        Tuple of return code, stdout and stderr.
    """
    action: Action = await unit.run(command, timeout)

    # For compatibility with juju 2.
    if on_juju_2():
        return (
            int(action.results["Code"]),
            action.results.get("Stdout", None),
            action.results.get("Stderr", None),
        )

    await action.wait()
    return (
        action.results["return-code"],
        action.results.get("stdout", None),
        action.results.get("stderr", None),
    )


async def run_in_lxd_instance(
    unit: Unit,
    name: str,
    command: str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: int | None = None,
) -> tuple[int, str | None, str | None]:
    """Run command in LXD instance of a juju unit.

    Args:
        unit: Juju unit to execute the command in.
        name: Name of LXD instance.
        command: Command to execute.
        env: Mapping of environment variable name to value.
        cwd: Work directory of the command.
        timeout: Amount of time to wait for the execution.

    Returns:
        Tuple of return code and stdout.
    """
    lxc_cmd = f"/snap/bin/lxc exec {name}"
    if env:
        for key, value in env.items():
            lxc_cmd += f"--env {key}={value}"
    if cwd:
        lxc_cmd += f" --cwd {cwd}"
    lxc_cmd += f" -- {command}"
    return await run_in_unit(unit, lxc_cmd, timeout)


async def start_test_http_server(unit: Unit, port: int):
    """Start test http server.

    Args:
        unit: The unit to start the test server in.
        port: Http server port.
    """
    await run_in_unit(
        unit,
        f"""cat <<EOT >> /etc/systemd/system/test-http-server.service
[Unit]
Description=Simple HTTP server for testing
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu
ExecStart=python3 -m http.server {port}
EOT""",
    )
    await run_in_unit(unit, "/usr/bin/systemctl daemon-reload")
    await run_in_unit(unit, "/usr/bin/systemctl start test-http-server")

    # Test the HTTP server
    for _ in range(10):
        return_code, stdout, _ = await run_in_unit(unit, f"curl http://localhost:{port}")
        if return_code == 0 and stdout:
            break
        await sleep(3)
    else:
        assert False, "Timeout waiting for HTTP server to start up"


async def set_app_runner_amount(app: Application, model: Model, num_runners: int) -> None:
    """Reconcile the application to a runner amount.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
        num_runners: The number of runners.
    """
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: f"{num_runners}"})
    await reconcile(app=app, model=model)
    await wait_till_num_of_runners(unit=app.units[0], num=num_runners)


async def ensure_charm_has_runner(app: Application, model: Model) -> None:
    """Reconcile the charm to contain one runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
    """
    await set_app_runner_amount(app, model, 1)


async def get_runner_name(unit: Unit) -> str:
    """Get the name of the runner.

    Expects only one runner to be present.

    Args:
        unit: The GitHub Runner Charm unit to get the runner name for.

    Returns:
        The Github runner name deployed in the given unit.
    """
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    return runners[0]


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
    runner_storage: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
    reconcile_interval: int,
    constraints: dict | None = None,
    config: dict | None = None,
    wait_idle: bool = True,
) -> Application:
    """Deploy github-runner charm.

    Args:
        model: Model to deploy the charm.
        charm_file: Path of the charm file to deploy.
        app_name: Application name for the deployment.
        path: Path representing the GitHub repo/org.
        token: GitHub Personal Token for the application to use.
        runner_storage: Runner storage to use, i.e. "memory" or "juju_storage",
        http_proxy: HTTP proxy for the application to use.
        https_proxy: HTTPS proxy for the application to use.
        no_proxy: No proxy configuration for the application.
        reconcile_interval: Time between reconcile for the application.
        constraints: The custom machine constraints to use. See DEFAULT_RUNNER_CONSTRAINTS
            otherwise.
        config: Additional custom config to use.
        wait_idle: wait for model to become idle.

    Returns:
        The charm application that was deployed.
    """
    # subprocess.run(["sudo", "modprobe", "br_netfilter"])

    # await model.set_config(
    #     {
    #         "juju-http-proxy": http_proxy,
    #         "juju-https-proxy": https_proxy,
    #         "juju-no-proxy": no_proxy,
    #         "logging-config": "<root>=INFO;unit=DEBUG",
    #     }
    # )

    storage = {}
    if runner_storage == "juju-storage":
        storage["runner"] = {"pool": "rootfs", "size": 11}

    default_config = {
        PATH_CONFIG_NAME: path,
        TOKEN_CONFIG_NAME: token,
        VIRTUAL_MACHINES_CONFIG_NAME: 0,
        # DENYLIST_CONFIG_NAME: "10.10.0.0/16",
        TEST_MODE_CONFIG_NAME: "insecure",
        RECONCILE_INTERVAL_CONFIG_NAME: reconcile_interval,
        RUNNER_STORAGE_CONFIG_NAME: runner_storage,
    }

    if config:
        default_config.update(config)

    application = await model.deploy(
        charm_file,
        application_name=app_name,
        series="jammy",
        config=default_config,
        constraints=constraints or DEFAULT_RUNNER_CONSTRAINTS,
        storage=storage,
    )

    if wait_idle:
        await model.wait_for_idle(status=ACTIVE, timeout=60 * 30)

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
    if run.update():
        return run.status == "completed"
    return False


async def dispatch_workflow(
    app: Application,
    branch: Branch,
    github_repository: Repository,
    conclusion: str,
    workflow_id_or_name: str,
    dispatch_input: dict | None = None,
):
    """Dispatch a workflow on a branch for the runner to run.

    The function assumes that there is only one runner running in the unit.

    Args:
        app: The charm to dispatch the workflow for.
        branch: The branch to dispatch the workflow on.
        github_repository: The github repository to dispatch the workflow on.
        conclusion: The expected workflow run conclusion.
        workflow_id_or_name: The workflow filename in .github/workflows in main branch to run or
            its id.
        dispatch_input: Workflow input values.

    Returns:
        A completed workflow.
    """
    start_time = datetime.now(timezone.utc)

    workflow = github_repository.get_workflow(id_or_file_name=workflow_id_or_name)

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(
        branch, dispatch_input or {"runner": app.name}
    ), "Failed to create workflow"

    # There is a very small chance of selecting a run not created by the dispatch above.
    run: WorkflowRun | None = await wait_for(
        partial(_get_latest_run, workflow=workflow, start_time=start_time, branch=branch)
    )
    assert run, f"Run not found for workflow: {workflow.name} ({workflow.id})"
    await wait_for(partial(_is_workflow_run_complete, run=run), timeout=60 * 30, check_interval=60)

    # The run object is updated by _is_workflow_run_complete function above.
    assert (
        run.conclusion == conclusion
    ), f"Unexpected run conclusion, expected: {conclusion}, got: {run.conclusion}"

    return workflow


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
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if is_awaitable:
        if result := await cast(Awaitable, func()):
            return result
    else:
        if result := func():
            return cast(R, result)
    raise TimeoutError()
