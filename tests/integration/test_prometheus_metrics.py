#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

import logging
from typing import Any, Generator, cast

import jubilant
import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from jubilant.statustypes import AppStatus
from juju.application import Application
from tenacity import retry, stop_after_attempt, wait_exponential

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    wait_for_reconcile,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper

logger = logging.getLogger(__name__)

MICROK8S_CONTROLLER_NAME = "microk8s"


@pytest_asyncio.fixture(scope="module", name="k8s_juju")
def k8s_juju_fixture(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """The machine model for K8s charms."""
    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models, controller=MICROK8S_CONTROLLER_NAME) as juju:
        yield juju


@pytest.fixture(scope="module", name="prometheus_app")
def prometheus_app_fixture(k8s_juju: jubilant.Juju):
    """Deploy prometheus charm."""
    k8s_juju.deploy("prometheus-k8s", channel="1/stable")
    k8s_juju.wait(lambda status: jubilant.all_active(status, "prometheus-k8s"))
    k8s_juju.offer(
        f"{k8s_juju.model}.prometheus-k8s",
        endpoint="receive-remote-write",
        controller=MICROK8S_CONTROLLER_NAME,
    )
    return k8s_juju.status().apps["prometheus-k8s"]


@pytest.fixture(scope="module", name="grafana_app")
def grafana_app_fixture(k8s_juju: jubilant.Juju, prometheus_app: AppStatus):
    """Deploy prometheus charm."""
    k8s_juju.deploy("grafana-k8s", channel="1/stable")
    k8s_juju.integrate("grafana-k8s:grafana-source", f"{prometheus_app.charm_name}:grafana-source")
    k8s_juju.wait(lambda status: jubilant.all_active(status, "grafana-k8s", "prometheus-k8s"))
    k8s_juju.offer(
        f"{k8s_juju.model}.grafana-k8s",
        endpoint="grafana-dashboard",
        controller=MICROK8S_CONTROLLER_NAME,
    )
    return k8s_juju.status().apps["grafana-k8s"]


@pytest.fixture(scope="module", name="traefik_ingress")
def traefik_ingress_fixture(
    k8s_juju: jubilant.Juju, prometheus_app: AppStatus, grafana_app: AppStatus
):
    """Ingress for cross controller communication."""
    k8s_juju.deploy("traefik-k8s", channel="latest/stable")
    k8s_juju.integrate("traefik-k8s", f"{prometheus_app.charm_name}:ingress")
    k8s_juju.integrate("traefik-k8s", f"{grafana_app.charm_name}:ingress")


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


@pytest.mark.usefixtures("traefik_ingress")
@pytest.mark.openstack
async def test_prometheus_metrics(
    juju: jubilant.Juju,
    k8s_juju: jubilant.Juju,
    openstack_app_cos_agent: Application,
    grafana_app: AppStatus,
    grafana_password: str,
    prometheus_app: AppStatus,
    test_github_branch: Branch,
    github_repository: Repository,
    instance_helper: OpenStackInstanceHelper,
):
    """
    arrange: given a prometheus charm application.
    act: when GitHub runner is integrated.
    assert: the datasource is registered and basic metrics are available.
    """
    prometheus_offer_name = "prometheus-k8s"
    grafana_offer_name = "grafana-k8s"
    # k8s_juju.model and juju.model already has <controller>: prefixed.
    juju.consume(
        f"{k8s_juju.model}.prometheus-k8s",
        alias="prometheus-k8s",
    )
    juju.consume(
        f"{k8s_juju.model}.grafana-k8s",
        alias="grafana-k8s",
    )

    juju.integrate("grafana-agent", prometheus_offer_name)
    juju.integrate("grafana-agent", grafana_offer_name)
    juju.wait(
        lambda status: jubilant.all_agents_idle(
            status, openstack_app_cos_agent.name, "grafana-agent"
        )
    )

    grafana_ip = grafana_app.units["grafana-k8s/0"].address
    _patiently_wait_for_prometheus_datasource(
        grafana_ip=grafana_ip, grafana_password=grafana_password
    )

    await instance_helper.ensure_charm_has_runner(openstack_app_cos_agent)
    await wait_for_reconcile(app=openstack_app_cos_agent)
    await dispatch_workflow(
        app=openstack_app_cos_agent,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )
    # Set the number of virtual machines to 0 to speedup reconciliation
    await openstack_app_cos_agent.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await wait_for_reconcile(app=openstack_app_cos_agent)

    prometheus_ip = prometheus_app.address
    _patiently_wait_for_prometheus_metrics(
        prometheus_ip,
        "openstack_http_requests_total",
        "reconcile_duration_seconds_sum",
        "expected_runners_count",
        "busy_runners_count",
        "idle_runners_count",
        "runner_spawn_duration_seconds_bucket",
        "runner_idle_duration_seconds_bucket",
        "runner_queue_duration_seconds_bucket",
        "deleted_runners_total",
        "delete_runner_duration_seconds_bucket",
        "deleted_vms_total",
        "delete_vm_duration_seconds_bucket",
        "job_duration_seconds_bucket",
        "job_status_count",
        "job_event_count",
    )


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, max=60), reraise=True)
def _patiently_wait_for_prometheus_datasource(grafana_ip: str, grafana_password: str):
    """Wait for prometheus datasource to come up."""
    response = requests.get(f"http://admin:{grafana_password}@{grafana_ip}:3000/api/datasources")
    response.raise_for_status()
    datasources: list[dict[str, Any]] = response.json()
    assert any(datasource["type"] == "prometheus" for datasource in datasources)


@retry(
    stop=stop_after_attempt(10), wait=wait_exponential(multiplier=2, min=10, max=60), reraise=True
)
def _patiently_wait_for_prometheus_metrics(prometheus_ip: str, *metric_names: str):
    """Wait for the prometheus metrics to be available."""
    for metric_name in metric_names:
        response = requests.get(
            f"http://{prometheus_ip}:9090/api/v1/series", params={"match[]": metric_name}
        )
        response.raise_for_status()
        query_result = response.json()["data"]
        assert len(query_result), f"No data found for metric: {metric_name}"
