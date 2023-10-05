#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics.

Expects a k8s controller to be available and its name is passed as option to pytest.
We need a k8s controller because we are using the loki-k8s charm to test the metrics.
k8s needs to have a loadbalancer enabled in order to be able to serve ingress with traefik. E.g.
metallb can be used for this purpose.

"""
import asyncio
import json
import logging
import secrets
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import requests
from juju.action import Action
from juju.application import Application
from juju.model import Controller, Model

from tests.integration.helpers import wait_till_num_of_runners
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.fixture(scope="module", name="k8s_controller_name")
def k8s_controller_name_fixture(pytestconfig: pytest.Config) -> str:
    """The k8s controller name."""
    controller_name = pytestconfig.getoption("--k8s-controller")
    assert controller_name, "Please specify the --k8s-controller command line option"
    return controller_name


@pytest_asyncio.fixture(scope="module", name="k8s_model")
async def k8s_model_fixture(k8s_controller_name: str) -> AsyncGenerator[Model, None]:
    """The k8s model for the COS stack."""
    controller = Controller()
    await controller.connect_controller(k8s_controller_name)

    k8s_model_name = f"obs-k8s-{secrets.token_hex(2)}"
    model = await controller.add_model(k8s_model_name)
    await model.connect(f"{k8s_controller_name}:admin/{model.name}")

    yield model

    await model.disconnect()
    await controller.destroy_models(k8s_model_name, destroy_storage=True)
    await controller.disconnect()


async def _get_logs_from_loki(loki: Application, traefik: Application) -> dict:
    """Get matching metric logs from Loki.

    Args:
        loki: The loki app.
        traefik: The traefik app.

    Returns:
        The logs from Loki as JSON.
    """
    traefik_unit = traefik.units[0]
    action: Action = await traefik_unit.run_action("show-proxied-endpoints")
    await action.wait()
    logging.info("Action results: %s", action.results)
    endpoints = json.loads(action.results["proxied-endpoints"])
    loki_endpoint = endpoints[f"{loki.name}/0"]["url"]
    resp = requests.get(
        f"{loki_endpoint}/loki/api/v1/query_range", params={"query": '{job="metrics"}'}
    )
    resp.raise_for_status()
    return resp.json()


async def _create_runner(app: Application, model: Model) -> None:
    """Let the charm create a runner.

    Args:
        app: The GitHub Runner Charmapp to create the runner for.
        model: The marchine charm model.
    """
    await app.set_config({"virtual-machines": "1"})
    unit = app.units[0]
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    await wait_till_num_of_runners(unit, 1)


async def _integrate_apps(
    app: Application,
    k8s_controller_name: str,
    k8s_model: Model,
    model: Model,
    loki: Application,
    traefik: Application,
    grafana_agent: Application,
) -> None:
    """Integrate all the apps together.

    1. traefik is integrated with loki.
    2. An offer for a cmr is created for loki:logging.
    3. The grafana-agent is integrated with the loki:logging offer.
    3. The charm is integrated with grafana-agent.

    Args:
        app: The GitHub Runner charm app to test.
        k8s_controller_name: The k8s controller name.
        k8s_model: The k8s model.
        model: The model.
        loki: The loki app.
        traefik: The traefik app.
        grafana_agent: The grafana-agent app.
    """
    await k8s_model.relate(traefik.name, f"{loki.name}:ingress")

    await k8s_model.create_offer(f"{loki.name}:logging")
    await k8s_model.wait_for_idle(
        apps=[loki.name], wait_for_active=True, idle_period=30, timeout=1200, check_freq=5
    )

    await model.relate(
        f"{grafana_agent.name}:logging-consumer",
        f"{k8s_controller_name}:admin/{k8s_model.name}.{loki.name}",
    )
    await model.wait_for_idle(apps=[grafana_agent.name], wait_for_active=True)
    await k8s_model.wait_for_idle(apps=[loki.name], wait_for_active=True)

    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], wait_for_active=True)


async def test_charm_issues_runner_installed_metric(
    model: Model,
    k8s_model: Model,
    k8s_controller_name: str,
    app_no_runner: Application,
):
    """
    arrange: A charm without runners integrated with Loki using the loki_push_api integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is issued.
    """
    loki = await k8s_model.deploy("loki-k8s", channel="latest/edge", trust=True)
    traefik = await k8s_model.deploy("traefik-k8s", channel="latest/edge", trust=True)
    grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
    await _integrate_apps(
        app=app_no_runner,
        k8s_controller_name=k8s_controller_name,
        k8s_model=k8s_model,
        model=model,
        loki=loki,
        traefik=traefik,
        grafana_agent=grafana_agent,
    )

    await _create_runner(app=app_no_runner, model=model)

    # we wait some time to make sure the metric is issued
    await asyncio.sleep(180)

    resp_json = await _get_logs_from_loki(loki, traefik)
    # resp_json is a JSON response from Loki. A sample response:
    # {"status": "success", "data": {
    #     "resultType": "streams", "result": [
    #         {"stream": {"job": "metrics"}, "values": [
    #             ["1695628888470376179",
    #          "{\"timestamp\": 1695628888, \"flavor\": \"github-runner\",
    #          \"duration\": 173, \"name\": \"runner_installed\"}"]
    #         ]}
    #     ],
    #   ...
    # }}

    assert resp_json["data"]["result"]
    assert resp_json["data"]["result"][0]["values"]

    metric_log_str = resp_json["data"]["result"][0]["values"][0][1]
    logging.info("Metric log: %s", metric_log_str)
    metric_log = json.loads(metric_log_str)
    assert metric_log.get("flavor") == app_no_runner.name
    assert metric_log.get("event") == "runner_installed"
    assert metric_log.get("duration") >= 0
