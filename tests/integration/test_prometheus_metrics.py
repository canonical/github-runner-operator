#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

import logging
import secrets
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import requests
from juju.application import Application
from juju.controller import Controller
from juju.model import Model
from pytest_operator.plugin import OpsTest
from tenacity import retry, stop_after_attempt, wait_exponential

from tests.integration.helpers.common import get_model_unit_addresses

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="k8s_controller")
async def k8s_controller_fixture() -> AsyncGenerator[Controller, None]:
    """The k8s controller.

    See scripts/setup-integration-tests.sh.
    """
    controller = Controller()
    await controller.connect_controller("microk8s")
    yield controller
    await controller.disconnect()


@pytest_asyncio.fixture(scope="module", name="k8s_model")
async def k8s_model_fixture(
    ops_test: OpsTest, k8s_controller: Controller
) -> AsyncGenerator[Model, None]:
    """The machine model for K8s charms."""
    k8s_model_name = f"k8s-{secrets.token_hex(2)}"
    model = await k8s_controller.add_model(k8s_model_name)
    logger.info("Added model: %s", model.name)
    await model.connect(f"microk8s:admin/{model.name}")
    yield model
    if ops_test.keep_model:
        return
    await k8s_controller.destroy_models(
        model.name, destroy_storage=True, force=True, max_wait=10 * 60
    )


@pytest_asyncio.fixture(scope="module", name="prometheus_app")
async def prometheus_app_fixture(k8s_model: Model):
    """Deploy prometheus charm."""
    prometheus_app: Application = await k8s_model.deploy("prometheus-k8s", channel="1/stable")
    await k8s_model.wait_for_idle(apps=[prometheus_app.name])
    return prometheus_app


@pytest_asyncio.fixture(scope="module", name="openstack_app_cos_agent")
async def openstack_app_cos_agent_fixture(app_openstack_runner: Application):
    """Deploy cos-agent subordinate charm on OpenStack runner application."""
    model = app_openstack_runner.model
    grafana_agent = await model.deploy("grafana-agent")
    await model.relate(grafana_agent.name, app_openstack_runner.name)
    await model.wait_for_idle(
        apps=[grafana_agent.name, app_openstack_runner.name], raise_on_error=False
    )
    return app_openstack_runner


@pytest.mark.openstack
async def test_prometheus_metrics(
    model: Model,
    k8s_model: Model,
    openstack_app_cos_agent_fixture: Application,
    prometheus_app: Application,
):
    """
    arrange: given a prometheus charm application.
    act: when GitHub runner is integrated.
    assert: the datasource is registered and basic metrics are available.
    """
    offer_name = "metrics"
    await k8s_model.create_offer(f"{prometheus_app.name}:metrics-endpoint", offer_name)
    await model.consume(f"microk8s:admin/{k8s_model.name}.{offer_name}")
    await model.integrate(openstack_app_cos_agent_fixture.name, offer_name)
    await k8s_model.wait_for_idle(apps=[prometheus_app.name], raise_on_error=False, timeout=300)
    await model.wait_for_idle(
        apps=[openstack_app_cos_agent_fixture.name], raise_on_error=False, timeout=300
    )

    addresses = await get_model_unit_addresses(model=k8s_model, app_name=prometheus_app.name)
    assert addresses, f"Unit addresses not found for {prometheus_app.name}"
    address = addresses[0]

    _assert_app_in_prometheus_target_patiently(
        prometheus_ip=address, target_name=openstack_app_cos_agent_fixture.name
    )
    _assert_metrics_in_prometheus_labels_patiently(prometheus_ip=address, labels=["flavor"])


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def _assert_app_in_prometheus_target_patiently(prometheus_ip: str, target_name: str):
    response = requests.get(f"http://{prometheus_ip}:9090/api/v1/targets", timeout=10).json()
    assert any(
        [
            target["labels"]["juju_charm"] == target_name
            for target in response["data"]["activeTargets"]
        ]
    )


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def _assert_metrics_in_prometheus_labels_patiently(prometheus_ip: str, labels: list[str]):
    response = requests.get(f"http://{prometheus_ip}:9090/api/v1/labels", timeout=10).json()
    assert set(labels).issubset(set(response["data"]))
