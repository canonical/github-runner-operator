#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics/logs assuming no Github workflow failures."""

import json
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import PATH_CONFIG_NAME, VIRTUAL_MACHINES_CONFIG_NAME
from metrics.runner import PostJobStatus
from tests.integration.helpers.charm_metrics import (
    assert_events_after_reconciliation,
    clear_metrics_log,
    get_metrics_log,
    print_loop_device_info,
)
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    InstanceHelper,
    dispatch_workflow,
    reconcile,
    run_in_unit,
)
from tests.integration.helpers.lxd import ensure_charm_has_runner, get_runner_name


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model, app_with_grafana_agent: Application, loop_device: str
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_with_grafana_agent.units[0]
    await clear_metrics_log(unit)
    await print_loop_device_info(unit, loop_device)
    yield app_with_grafana_agent


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_runner_installed_metric(
    app: Application, model: Model, instance_helper: InstanceHelper
):
    """
    arrange: A charm integrated with grafana-agent using the cos-agent integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is logged.
    """
    await instance_helper.ensure_charm_has_runner(app)

    metrics_log = await get_metrics_log(app.units[0])
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    events = set(map(lambda line: line.get("event"), log_lines))
    assert "runner_installed" in events, "runner_installed event has not been logged"

    for metric_log in log_lines:
        if metric_log.get("event") == "runner_installed":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("event") == "runner_installed"
            assert metric_log.get("duration") >= 0


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_after_reconciliation(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
    instance_helper: InstanceHelper,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a workflow on a branch for the runner to run. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to normal.
    """
    await app.set_config({PATH_CONFIG_NAME: forked_github_repository.full_name})
    await instance_helper.ensure_charm_has_runner(app)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await clear_metrics_log(unit)
    await dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app, github_repository=forked_github_repository, post_job_status=PostJobStatus.NORMAL
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_remounts_shared_fs(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow and afterwards unmount the shared fs. After that, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
    """
    await app.set_config({PATH_CONFIG_NAME: forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    runner_name = await get_runner_name(unit)
    await clear_metrics_log(unit)
    await dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )

    # unmount shared fs
    await run_in_unit(unit, f"sudo umount /home/ubuntu/runner-fs/{runner_name}")

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app, github_repository=forked_github_repository, post_job_status=PostJobStatus.NORMAL
    )
