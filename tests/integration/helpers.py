# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import inspect
import json
import subprocess
import time
import typing
from asyncio import sleep
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Union

import github
import juju.version
import requests
import yaml
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowJob import WorkflowJob
from github.WorkflowRun import WorkflowRun
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from runner import Runner
from runner_manager import RunnerManager
from tests.status_name import ACTIVE
from utilities import retry

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME = "workflow_dispatch_failure_test.yaml"
DISPATCH_WAIT_TEST_WORKFLOW_FILENAME = "workflow_dispatch_wait_test.yaml"
DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME = "e2e_test_run.yaml"


async def check_runner_binary_exists(unit: Unit) -> bool:
    """Checks if runner binary exists in the charm.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        Whether the runner binary file exists in the charm.
    """
    return_code, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    return return_code == 0


async def get_repo_policy_compliance_pip_info(unit: Unit) -> None | str:
    """Get pip info for repo-policy-compliance.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        If repo-policy-compliance is installed, returns the pip show output, else returns none.
    """
    return_code, stdout = await run_in_unit(unit, "python3 -m pip show repo-policy-compliance")

    if return_code == 0:
        return stdout

    return None


async def install_repo_policy_compliance_from_git_source(unit: Unit, source: None | str) -> None:
    """Install repo-policy-compliance pip package from the git source.

    Args:
        unit: Unit instance to check for the LXD profile.
        source: The git source to install the package. If none the package is removed.
    """
    return_code, stdout = await run_in_unit(
        unit, "python3 -m pip uninstall --yes repo-policy-compliance"
    )
    assert return_code == 0, f"Failed to uninstall repo-policy-compliance: {stdout}"

    if source:
        return_code, _ = await run_in_unit(unit, f"python3 -m pip install {source}")
        assert return_code == 0


async def remove_runner_bin(unit: Unit) -> None:
    """Remove runner binary.

    Args:
        unit: Unit instance to check for the LXD profile.
    """
    await run_in_unit(unit, f"rm {RunnerManager.runner_bin_path}")

    # No file should exists under with the filename.
    return_code, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    assert return_code != 0


async def assert_resource_lxd_profile(unit: Unit, configs: dict[str, Any]) -> None:
    """Check for LXD profile of the matching resource config.

    Args:
        unit: Unit instance to check for the LXD profile.
        configs: Configs of the application.

    Raises:
        AssertionError: Unable to find an LXD profile with matching resource
            config.
    """
    cpu = configs["vm-cpu"]["value"]
    mem = configs["vm-memory"]["value"]
    disk = configs["vm-disk"]["value"]
    resource_profile_name = Runner._get_resource_profile_name(cpu, mem, disk)

    # Verify the profile exists.
    return_code, stdout = await run_in_unit(unit, "lxc profile list --format json")
    assert return_code == 0
    assert stdout is not None
    profiles = json.loads(stdout)
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    return_code, stdout = await run_in_unit(unit, f"lxc profile show {resource_profile_name}")
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
    return_code, stdout = await run_in_unit(unit, "lxc list --format json")

    assert return_code == 0
    assert stdout is not None

    lxc_instance: list[dict[str, str]] = json.loads(stdout)
    return tuple(runner["name"] for runner in lxc_instance)


@retry(tries=30, delay=30)
async def wait_till_num_of_runners(unit: Unit, num: int) -> None:
    """Wait and check the number of runners.

    Args:
        unit: Unit instance to check for the LXD profile.
        num: Number of runner instances to check for.

    Raises:
        AssertionError: Correct number of runners is not found within timeout
            limit.
    """
    return_code, stdout = await run_in_unit(unit, "lxc list --format json")
    assert return_code == 0
    assert stdout is not None

    lxc_instance = json.loads(stdout)
    assert (
        len(lxc_instance) == num
    ), f"Current number of runners: {len(lxc_instance)} Expected number of runner: {num}"

    for instance in lxc_instance:
        return_code, stdout = await run_in_unit(unit, f"lxc exec {instance['name']} -- ps aux")
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


async def run_in_unit(unit: Unit, command: str, timeout=None) -> tuple[int, str | None]:
    """Run command in juju unit.

    Compatible with juju 3 and juju 2.

    Args:
        unit: Juju unit to execute the command in.
        command: Command to execute.
        timeout: Amount of time to wait for the execution.

    Returns:
        Tuple of return code and stdout.
    """
    action = await unit.run(command, timeout)

    # For compatibility with juju 2.
    if on_juju_2():
        return (int(action.results["Code"]), action.results.get("Stdout", None))

    await action.wait()
    return (action.results["return-code"], action.results.get("stdout", None))


async def run_in_lxd_instance(
    unit: Unit,
    name: str,
    command: str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: int | None = None,
) -> tuple[int, str | None]:
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
        return_code, stdout = await run_in_unit(unit, f"curl http://localhost:{port}")
        if return_code == 0 and stdout:
            break
        await sleep(3)
    else:
        assert False, "Timeout waiting for HTTP server to start up"


async def ensure_charm_has_runner(app: Application, model: Model) -> None:
    """Reconcile the charm to contain one runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
    """
    await app.set_config({"virtual-machines": "1"})
    await reconcile(app=app, model=model)
    await wait_till_num_of_runners(unit=app.units[0], num=1)


async def get_runner_name(unit: Unit) -> str:
    """Get the name of the runner.

    Expects only one runner to be present.

    Args:
        unit: The GitHub Runner Charm unit to get the runner name for.
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
        wait_idle: wait for model to become idle.
    """
    subprocess.run(["sudo", "modprobe", "br_netfilter"])

    await model.set_config(
        {
            "juju-http-proxy": http_proxy,
            "juju-https-proxy": https_proxy,
            "juju-no-proxy": no_proxy,
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    storage = {}
    if runner_storage == "juju-storage":
        storage["runner"] = {"pool": "rootfs", "size": 11}

    application = await model.deploy(
        charm_file,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "token": token,
            "virtual-machines": 0,
            "denylist": "10.10.0.0/16",
            "test-mode": "insecure",
            "reconcile-interval": reconcile_interval,
            "runner-storage": runner_storage,
        },
        constraints={"root-disk": "20G", "cores": 4, "mem": "10G", "virt-type": "virtual-machine"},
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
    """
    if branch is None:
        branch = github.GithubObject.NotSet

    for run in workflow.get_runs(created=f">={start_time.isoformat()}", branch=branch):
        latest_job: WorkflowJob = run.jobs()[0]
        logs = get_job_logs(job=latest_job)

        if runner_name in logs:
            yield run


async def _wait_until_runner_is_used_up(runner_name: str, unit: Unit):
    """Wait until the runner is used up.

    Args:
        runner_name: The runner name to wait for.
        unit: The unit which contains the runner.
    """
    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner_name not in runners:
            break
        await sleep(30)
    else:
        assert False, "Timeout while waiting for the runner to be used up"


async def _assert_workflow_run_conclusion(
    runner_name: str, conclusion: str, workflow: Workflow, start_time: datetime
):
    """Assert that the workflow run has the expected conclusion.

    Args:
        runner_name: The runner name to assert the workflow run conclusion for.
        conclusion: The expected workflow run conclusion.
        workflow: The workflow to assert the workflow run conclusion for.
        start_time: The start time of the workflow.
    """
    log_found = False
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        latest_job: WorkflowJob = run.jobs()[0]
        logs = get_job_logs(job=latest_job)

        if runner_name in logs:
            log_found = True
            assert latest_job.conclusion == conclusion, (
                f"Job {latest_job.name} for {runner_name} expected {conclusion}, "
                f"got {latest_job.conclusion}"
            )

    assert log_found, (
        f"No run with runner({runner_name}) log found for workflow({workflow.name}) "
        f"starting from {start_time} with conclusion {conclusion}"
    )


async def _wait_for_workflow_to_complete(
    unit: Unit, workflow: Workflow, conclusion: str, start_time: datetime
):
    """Wait for the workflow to complete.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to wait for.
        conclusion: The workflow conclusion to wait for.
        start_time: The start time of the workflow.
    """
    runner_name = await get_runner_name(unit)
    await _wait_until_runner_is_used_up(runner_name, unit)
    # Wait for the workflow log to contain the conclusion
    await sleep(120)

    await _assert_workflow_run_conclusion(
        runner_name=runner_name, conclusion=conclusion, workflow=workflow, start_time=start_time
    )


async def dispatch_workflow(
    app: Application,
    branch: Branch,
    github_repository: Repository,
    conclusion: str,
    workflow_id_or_name: str,
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

    Returns:
        A completed workflow.
    """
    start_time = datetime.now(timezone.utc)

    workflow = github_repository.get_workflow(id_or_file_name=workflow_id_or_name)

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, {"runner": app.name})
    await _wait_for_workflow_to_complete(
        unit=app.units[0], workflow=workflow, conclusion=conclusion, start_time=start_time
    )
    return workflow


async def wait_for(
    func: Callable[[], Union[Awaitable, Any]],
    timeout: int = 300,
    check_interval: int = 10,
) -> Any:
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
            if result := await func():
                return result
        else:
            if result := func():
                return result
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if is_awaitable:
        if result := await func():
            return result
    else:
        if result := func():
            return result
    raise TimeoutError()
