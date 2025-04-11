#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics/logs assuming no Github workflow failures."""

import json
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from github_runner_manager.manager.cloud_runner_manager import PostJobStatus
from juju.application import Application
from juju.model import Model

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    assert_events_after_reconciliation,
    clear_metrics_log,
    get_metrics_log,
)
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    reconcile,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(model: Model, app_for_metric: Application) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_for_metric.units[0]
    await clear_metrics_log(unit)

    yield app_for_metric


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_runner_installed_metric(
    app: Application, model: Model, instance_helper: OpenStackInstanceHelper
):
    """
    arrange: A charm integrated with grafana-agent using the cos-agent integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is logged.
    """
    await instance_helper.ensure_charm_has_runner(app)

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

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
    github_repository: Repository,
    test_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a workflow on a branch for the runner to run. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to normal.
    """
    await instance_helper.ensure_charm_has_runner(app)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await clear_metrics_log(unit)
    await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app, github_repository=github_repository, post_job_status=PostJobStatus.NORMAL
    )
