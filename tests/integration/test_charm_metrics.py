#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics."""
import json
import logging

from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from metrics import METRICS_LOG_PATH
from tests.integration.helpers import wait_till_num_of_runners
from tests.status_name import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME


async def _create_runner(app: Application, model: Model) -> None:
    """Let the charm create a runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The marchine charm model.
    """
    await app.set_config({"virtual-machines": "1"})
    unit = app.units[0]
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)
    await wait_till_num_of_runners(unit, 1)


async def _get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    return await unit.ssh(f"cat {METRICS_LOG_PATH}")


async def test_charm_issues_runner_installed_metric(
    model: Model,
    app_no_runner: Application,
):
    """
    arrange: A charm without runners integrated with grafana-agent using the cos-agent integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is logged.
    """
    app = app_no_runner  # alias for readability as the app will have a runner during the test
    grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)
    # Grafana-Agent will block because it requires an additional integration like logging-consumer,
    # but we don't need it for this test.
    await model.wait_for_idle(apps=[grafana_agent.name], status=BLOCKED_STATUS_NAME)

    await _create_runner(app=app, model=model)

    metrics_log = await _get_metrics_log(app.units[0])
    logging.info("Metric log: %s", metrics_log)
    metric_log = json.loads(metrics_log)
    assert metric_log.get("flavor") == app.name
    assert metric_log.get("event") == "runner_installed"
    assert metric_log.get("duration") >= 0
