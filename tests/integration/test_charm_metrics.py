#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics."""
import json
import logging
from time import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from metrics import METRICS_LOG_PATH
from runner_metrics import PostJobStatus
from tests.integration.helpers import (
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_name,
    get_runner_names,
    reconcile,
    run_in_unit,
)
from tests.status_name import ACTIVE_STATUS_NAME

TEST_WORKFLOW_NAME = "Workflow Dispatch Tests"


@pytest_asyncio.fixture(scope="module", name="app_integrated")
async def app_integrated_fixture(
    model: Model, app_no_runner: Application
) -> AsyncIterator[Application]:
    """Setup the charm to be integrated with grafana-agent using the cos-agent integration."""
    await _integrate_apps(app_no_runner, model)

    yield app_no_runner


async def _clear_metrics_log(unit: Unit) -> None:
    """Clear the metrics log on the unit.

    Args:
        unit: The unit to clear the metrics log on.
    """
    retcode, _ = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then rm {METRICS_LOG_PATH}; fi",
    )
    assert retcode == 0, "Failed to clear metrics log"


async def _print_loop_device_info(unit: Unit, loop_device: str) -> None:
    """Print loop device info on the unit.

    Args:
        unit: The unit to print the loop device info on.
        loop_device: The loop device to print the info for.
    """
    retcode, stdout = await run_in_unit(
        unit=unit,
        command="sudo losetup -lJ",
    )
    assert retcode == 0, f"Failed to get loop devices: {stdout}"
    assert stdout is not None, "Failed to get loop devices, no stdout message"
    loop_devices_info = json.loads(stdout)
    for loop_device_info in loop_devices_info["loopdevices"]:
        if loop_device_info["name"] == loop_device:
            logging.info("Loop device %s info: %s", loop_device, loop_device_info)
            break
    else:
        logging.info("Loop device %s not found", loop_device)


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model, app_integrated: Application, loop_device: str
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_integrated.units[0]
    await _clear_metrics_log(unit)
    await _print_loop_device_info(unit, loop_device)
    yield app_integrated


async def _get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    retcode, stdout = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then cat {METRICS_LOG_PATH}; else echo ''; fi",
    )
    assert retcode == 0, f"Failed to get metrics log: {stdout}"
    assert stdout is not None, "Failed to get metrics log, no stdout message"
    logging.info("Metrics log: %s", stdout)
    return stdout.strip()


async def _integrate_apps(app: Application, model: Model):
    """Integrate the charm with grafana-agent using the cos-agent integration.

    Args:
        app: The charm to integrate.
        model: The model to deploy the grafana-agent to.
    """
    grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)
    await model.wait_for_idle(apps=[grafana_agent.name])


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
        sleep(30)
    else:
        assert False, "Timeout while waiting for the runner to be used up"


async def _assert_workflow_run_conclusion(runner_name: str, conclusion: str, workflow: Workflow):
    """Assert that the workflow run has the expected conclusion.

    Args:
        runner_name: The runner name to assert the workflow run conclusion for.
        conclusion: The expected workflow run conclusion.
        workflow: The workflow to assert the workflow run conclusion for.
    """
    for run in workflow.get_runs():
        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if f"Job is about to start running on the runner: {runner_name}" in logs:
            assert run.jobs()[0].conclusion == conclusion


async def _wait_for_workflow_to_complete(unit: Unit, workflow: Workflow, conclusion: str):
    """Wait for the workflow to complete.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to wait for.
        conclusion: The workflow conclusion to wait for.
    """
    runner_name = await get_runner_name(unit)
    await _wait_until_runner_is_used_up(runner_name, unit)
    # Wait for the workflow log to contain the conclusion
    sleep(60)

    await _assert_workflow_run_conclusion(runner_name, conclusion, workflow)


async def _dispatch_workflow(
    app: Application, branch: Branch, github_repository: Repository, conclusion: str
):
    """Dispatch a workflow on a branch for the runner to run.

    The function assumes that there is only one runner running in the unit.

    Args:
        app: The charm to dispatch the workflow for.
        branch: The branch to dispatch the workflow on.
        github_repository: The github repository to dispatch the workflow on.
        conclusion: The expected workflow run conclusion.
    """
    workflow = github_repository.get_workflow(id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME)
    if conclusion == "failure":
        workflow = github_repository.get_workflow(
            id_or_file_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME
        )

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, {"runner": app.name})
    await _wait_for_workflow_to_complete(
        unit=app.units[0], workflow=workflow, conclusion=conclusion
    )


async def _assert_events_after_reconciliation(
    app: Application, github_repository: Repository, post_job_status: PostJobStatus
):
    """Assert that the RunnerStart, RunnerStop and Reconciliation metric is logged.

    Args:
        app: The charm to assert the events for.
        github_repository: The github repository to assert the events for.
        post_job_status: The expected post job status of the reconciliation event.
    """
    unit = app.units[0]

    metrics_log = await _get_metrics_log(unit=unit)
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    events = set(map(lambda line: line.get("event"), log_lines))
    assert {
        "runner_start",
        "runner_stop",
        "reconciliation",
    } <= events, "Not all events were logged"
    for metric_log in log_lines:
        if metric_log.get("event") == "runner_start":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("workflow") == TEST_WORKFLOW_NAME
            assert metric_log.get("repo") == github_repository.full_name
            assert metric_log.get("github_event") == "workflow_dispatch"
            assert metric_log.get("idle") >= 0
        if metric_log.get("event") == "runner_stop":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("workflow") == TEST_WORKFLOW_NAME
            assert metric_log.get("repo") == github_repository.full_name
            assert metric_log.get("github_event") == "workflow_dispatch"
            assert metric_log.get("status") == post_job_status
            assert metric_log.get("job_duration") >= 0
        if metric_log.get("event") == "reconciliation":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("duration") >= 0
            assert metric_log.get("crashed_runners") == 0
            assert metric_log.get("idle_runners") == 0
            assert metric_log.get("active_runners") == 0


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_runner_installed_metric(app: Application, model: Model):
    """
    arrange: A charm without runners integrated with grafana-agent using the cos-agent integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is logged.
    """

    await ensure_charm_has_runner(app=app, model=model)

    metrics_log = await _get_metrics_log(app.units[0])
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    events = set(map(lambda line: line.get("event"), log_lines))
    assert "runner_installed" in events, "runner_installed event has not been logged"

    for metric_log in log_lines:
        if metric_log.get("event") == "runner_installed":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("event") == "runner_installed"
            assert metric_log.get("duration") >= 0


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_after_reconciliation(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a workflow on a branch for the runner to run. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to normal.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await _clear_metrics_log(unit)
    await _dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="success",
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
        app=app, github_repository=forked_github_repository, post_job_status=PostJobStatus.NORMAL
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_for_failed_runner(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow that fails the repo-policy check. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to failure.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await _clear_metrics_log(unit)
    await _dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="failure",
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
        app=app,
        github_repository=forked_github_repository,
        post_job_status=PostJobStatus.REPO_POLICY_CHECK_FAILURE,
    )
