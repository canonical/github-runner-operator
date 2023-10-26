#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics."""
import json
import logging
from time import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from metrics import METRICS_LOG_PATH
from tests.integration.helpers import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_name,
    get_runner_names,
    reconcile,
    run_in_unit,
)
from tests.status_name import ACTIVE_STATUS_NAME


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
    metric_log = json.loads(metrics_log)
    assert metric_log.get("flavor") == app.name
    assert metric_log.get("event") == "runner_installed"
    assert metric_log.get("duration") >= 0


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_runner_metrics_during_reconciliation(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    branch_with_protection: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a workflow on a branch for the runner to run. After completion, reconcile.
    assert: The RunnerStart metric is logged.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
    )
    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch_with_protection, {"runner": app.name})
    unit = app.units[0]
    await _wait_until_runner_is_used_up(unit=unit)
    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    metrics_log = await _get_metrics_log(unit=unit)
    log_lines = map(lambda line: json.loads(line), metrics_log.splitlines())
    for metric_log in log_lines:
        if metric_log.get("event") == "runner_start":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("workflow") == "Workflow Dispatch Tests"
            assert metric_log.get("repo") == forked_github_repository.full_name
            assert metric_log.get("github_event") == "workflow_dispatch"
            assert metric_log.get("idle") >= 0
            break
    else:
        assert False, "No runner_start metric found"
