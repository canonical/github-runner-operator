#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics."""
import json
import logging

from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from metrics import METRICS_LOG_PATH
from tests.integration.helpers import create_runner
from tests.status_name import ACTIVE_STATUS_NAME


async def _get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    return (await unit.ssh(
        f"if [ -f {METRICS_LOG_PATH} ]; then cat {METRICS_LOG_PATH}; else echo ''; fi"
    )).strip()


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
    await model.wait_for_idle(apps=[grafana_agent.name])
    metrics_log = await _get_metrics_log(app.units[0])
    assert metrics_log == "".strip()

    await create_runner(app=app, model=model)

    metrics_log = await _get_metrics_log(app.units[0])
    logging.info("Metric log: %s", metrics_log)
    metric_log = json.loads(metrics_log)
    assert metric_log.get("flavor") == app.name
    assert metric_log.get("event") == "runner_installed"
    assert metric_log.get("duration") >= 0
