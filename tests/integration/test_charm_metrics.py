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
    DISPATCH_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_name,
    get_runner_names,
    reconcile,
    run_in_unit,
)
from tests.status_name import ACTIVE_STATUS_NAME

TEST_WORKFLOW_NAME = "Workflow Dispatch Tests"


@pytest.fixture(scope="module", name="branch_with_protection")
def branch_with_protection_fixture(forked_github_branch: Branch):
    """Add required branch protection to the branch."""

    forked_github_branch.edit_protection()
    forked_github_branch.add_required_signatures()

    yield forked_github_branch

    forked_github_branch.remove_protection()


async def _clear_metrics_log(unit: Unit):
    retcode, _ = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then rm {METRICS_LOG_PATH}; fi",
    )
    assert retcode == 0, "Failed to clear metrics log"


@pytest_asyncio.fixture(scope="module", name="app_integrated")
async def app_integrated_fixture(
    model: Model, app_no_runner: Application
) -> AsyncIterator[Application]:
    """Setup the charm to be integrated with grafana-agent using the cos-agent integration."""
    await _integrate_apps(app_no_runner, model)

    yield app_no_runner


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(model: Model, app_integrated: Application) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure that the metrics log is empty and cleared after each test.
    """
    metrics_log = await _get_metrics_log(app_integrated.units[0])
    assert metrics_log == ""

    yield app_integrated

    await _clear_metrics_log(app_integrated.units[0])


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


async def _wait_until_runner_is_used_up(unit: Unit):
    """Wait until the runner is used up.

    Args:
        unit: The unit which contains the runner.
    """
    runner = await get_runner_name(unit)

    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner not in runners:
            break
        sleep(30)
    else:
        assert False, "Timeout while waiting for the runner to be used up"


async def _assert_workflow_run_conclusion(app: Application, conclusion: str, workflow: Workflow):
    """Assert that the workflow run has the expected conclusion.

    Args:
        app: The charm to assert the workflow run conclusion for.
        conclusion: The expected workflow run conclusion.
        workflow: The workflow to assert the workflow run conclusion for.
    """
    for run in workflow.get_runs():
        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if f"Job is about to start running on the runner: {app.name}-" in logs:
            assert run.jobs()[0].conclusion == conclusion


async def _wait_for_workflow_to_complete(app: Application, workflow: Workflow, conclusion: str):
    """Wait for the workflow to complete.

    Args:
        app: The charm to wait for the workflow to complete.
        workflow: The workflow to wait for.
        conclusion: The workflow conclusion to wait for.
    """
    await _wait_until_runner_is_used_up(app.units[0])
    # Wait for the workflow log to contain the conclusion
    sleep(60)

    await _assert_workflow_run_conclusion(app, conclusion, workflow)


async def _dispatch_workflow(
    app: Application, branch: Branch, github_repository: Repository, conclusion: str
):
    """Dispatch a workflow on a branch for the runner to run.

    Args:
        app: The charm to dispatch the workflow for.
        branch: The branch to dispatch the workflow on.
        github_repository: The github repository to dispatch the workflow on.
        conclusion: The expected workflow run conclusion.
    """
    workflow = github_repository.get_workflow(id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME)
    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, {"runner": app.name})
    await _wait_for_workflow_to_complete(app=app, workflow=workflow, conclusion=conclusion)


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
            assert metric_log.get("status") == PostJobStatus.NORMAL
            assert metric_log.get("job_duration") >= 0
        if metric_log.get("event") == "reconciliation":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("duration") >= 0
            assert metric_log.get("crashed_runners") == 0
            assert metric_log.get("idle_runners") == 0


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
    branch_with_protection: Branch,
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
        branch=branch_with_protection,
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
    act: Dispatch a workflow on a branch which has not been properly setup to pass
        the repo-policy check. After completion, reconcile.
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
