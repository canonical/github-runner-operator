#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

import logging
from typing import Generator, cast

import jubilant
import pytest
import pytest_asyncio
from jubilant.statustypes import AppStatus
from juju.application import Application

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="k8s_juju")
def k8s_juju_fixture(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """The machine model for K8s charms."""
    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models, controller="microk8s") as juju:
        # Currently juju has no way of switching controller context, this is required to operate
        # in the right controller's right model when using multiple controllers.
        # See: https://github.com/canonical/jubilant/issues/158
        juju.model = f"microk8s:{juju.model}"
        yield juju


@pytest.fixture(scope="module", name="prometheus_app")
def prometheus_app_fixture(k8s_juju: jubilant.Juju):
    """Deploy prometheus charm."""
    k8s_juju.deploy("prometheus-k8s", channel="1/stable")
    k8s_juju.wait(lambda status: jubilant.all_active(status, "prometheus-k8s"))
    k8s_juju.offer("prometheus-k8s", endpoint="receive-remote-write")
    return k8s_juju.status().apps["prometheus-k8s"]


@pytest.fixture(scope="module", name="grafana_app")
def grafana_app_fixture(k8s_juju: jubilant.Juju):
    """Deploy prometheus charm."""
    k8s_juju.deploy("grafana-k8s", channel="1/stable")
    k8s_juju.integrate("grafana-k8s:grafana-source", "prometheus-k8s:grafana-source")
    k8s_juju.wait(lambda status: jubilant.all_active(status, "grafana-k8s", "prometheus-k8s"))
    k8s_juju.offer("grafana-k8s", endpoint="grafana-dashboard")
    return k8s_juju.status().apps["grafana-k8s"]


@pytest.fixture(scope="module", name="grafana_password")
def grafana_password_fixture(k8s_juju: jubilant.Juju, grafana_app: AppStatus):
    """Get Grafana dashboard password."""
    unit = next(iter(grafana_app.units.keys()))
    result = k8s_juju.run(unit, "get-admin-password")
    return result.results["admin-password"]


@pytest.fixture(scope="module", name="openstack_app_cos_agent")
def openstack_app_cos_agent_fixture(juju: jubilant.Juju, app_openstack_runner: Application):
    """Deploy cos-agent subordinate charm on OpenStack runner application."""
    juju.deploy("grafana-agent", channel="1/stable", base="ubuntu@22.04")
    juju.integrate(app_openstack_runner.name, "grafana-agent")
    juju.wait(
        lambda status: jubilant.all_agents_idle(status, app_openstack_runner.name, "grafana-agent")
    )
    return app_openstack_runner


@pytest.mark.openstack
def test_prometheus_metrics(
    juju: jubilant.Juju,
    k8s_juju: jubilant.Juju,
    openstack_app_cos_agent: Application,
    grafana_app: AppStatus,
    grafana_password: str,
):
    """
    arrange: given a prometheus charm application.
    act: when GitHub runner is integrated.
    assert: the datasource is registered and basic metrics are available.
    """
    prometheus_offer_name = "prometheus-k8s"
    grafana_offer_name = "grafana-k8s"
    # k8s_juju.model already has <controller>: prefixed.
    juju.cli(f"consume {k8s_juju.model}.{prometheus_offer_name}")
    juju.cli(f"consume {k8s_juju.model}.{grafana_offer_name}")
    juju.integrate("grafana-agent", prometheus_offer_name)
    juju.integrate("grafana-agent", grafana_offer_name)
    juju.wait(
        lambda status: jubilant.all_agents_idle(
            status, openstack_app_cos_agent.name, "grafana-agent"
        )
    )
    grafana_ip = grafana_app.units["grafana-k8s/0"].address
    assert False, f"admin:{grafana_password}@{grafana_ip}:3000/"
