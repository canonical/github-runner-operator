#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Prometheus metrics integration test — subprocess variant.

Replaces jubilant CLI calls with direct subprocess calls that have hard timeouts
to work around jubilant#271 (_cli() can hang indefinitely when juju commands stall).
Compare behavior with the original test_prometheus_metrics.py to evaluate this approach.
"""

import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generator, cast

import jubilant
import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from tenacity import retry, stop_after_attempt, wait_exponential

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    wait_for,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.openstack, pytest.mark.timeout(2400)]

MICROK8S_CONTROLLER_NAME = "microk8s"
COS_AGENT_CHARM = "opentelemetry-collector"
CLI_TIMEOUT = 300
STATUS_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Subprocess helpers — every juju CLI call gets a hard subprocess timeout
# ---------------------------------------------------------------------------


def _juju_cli(
    *args: str, model: str | None = None, timeout: int = CLI_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run a juju CLI command with a hard subprocess timeout.

    Raises subprocess.TimeoutExpired if the command hangs.
    """
    cmd = ["juju", *args]
    if model:
        cmd.extend(["-m", model])
    logger.info("juju-cli: %s", " ".join(cmd))
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    logger.info("juju-cli: completed in %.1fs", time.monotonic() - t0)
    if result.stderr:
        logger.debug("juju-cli stderr: %s", result.stderr[:500])
    return result


def _juju_status(model: str, timeout: int = STATUS_TIMEOUT) -> dict[str, Any]:
    """Fetch and parse juju status as JSON."""
    result = _juju_cli("status", "--format", "json", model=model, timeout=timeout)
    return json.loads(result.stdout)


def _all_active(status: dict[str, Any], *app_names: str) -> bool:
    """Check all named apps and their units have active workload status."""
    apps = status.get("applications", {})
    for name in app_names:
        app = apps.get(name)
        if not app:
            return False
        if app.get("application-status", {}).get("current") != "active":
            return False
        for unit in app.get("units", {}).values():
            if unit.get("workload-status", {}).get("current") != "active":
                return False
    return True


def _all_agents_idle(status: dict[str, Any], *app_names: str) -> bool:
    """Check all agents (including subordinates) for named apps are idle."""
    apps = status.get("applications", {})
    for name in app_names:
        app = apps.get(name)
        if not app:
            return False
        for unit in app.get("units", {}).values():
            if unit.get("juju-status", {}).get("current") != "idle":
                return False
            for sub in unit.get("subordinates", {}).values():
                if sub.get("juju-status", {}).get("current") != "idle":
                    return False
    return True


def _wait_for_status(
    model: str,
    check: Callable[[dict[str, Any]], bool],
    *,
    timeout: int = 600,
    delay: int = 5,
    successes_needed: int = 3,
) -> dict[str, Any]:
    """Poll ``juju status`` until *check* returns True.

    Each individual ``juju status`` call has its own subprocess timeout so a
    single hung call cannot block the whole wait.
    """
    deadline = time.monotonic() + timeout
    consecutive = 0
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last_status = _juju_status(model, timeout=STATUS_TIMEOUT)
            if check(last_status):
                consecutive += 1
                if consecutive >= successes_needed:
                    return last_status
            else:
                consecutive = 0
        except subprocess.TimeoutExpired:
            logger.warning("juju status timed out for model %s, retrying", model)
            consecutive = 0
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "juju status failed for model %s (rc=%d): %s",
                model,
                exc.returncode,
                (exc.stderr or "")[:300],
            )
            consecutive = 0
        time.sleep(delay)
    raise TimeoutError(
        f"Condition not met within {timeout}s. "
        f"Last status apps: {list(last_status.get('applications', {}).keys())}"
    )


# ---------------------------------------------------------------------------
# Lightweight status types (replace jubilant.statustypes)
# ---------------------------------------------------------------------------


@dataclass
class UnitInfo:
    """Minimal unit info extracted from juju status JSON.

    Attributes:
        address: The unit's IP address.
    """

    address: str


@dataclass
class AppInfo:
    """Minimal app info extracted from juju status JSON.

    Attributes:
        name: The application name.
        charm_name: The charm name.
        address: The application's IP address.
        units: Mapping of unit name to UnitInfo.
    """

    name: str
    charm_name: str
    address: str
    units: dict[str, UnitInfo] = field(default_factory=dict)


def _app_info_from_status(status: dict[str, Any], app_name: str) -> AppInfo:
    """Build an AppInfo from parsed juju status JSON."""
    app = status["applications"][app_name]
    units: dict[str, UnitInfo] = {}
    first_unit_addr = ""
    for unit_name, unit_data in app.get("units", {}).items():
        addr = unit_data.get("address", "")
        units[unit_name] = UnitInfo(address=addr)
        if not first_unit_addr:
            first_unit_addr = addr
    return AppInfo(
        name=app_name,
        charm_name=app.get("charm-name", app_name),
        address=app.get("address", first_unit_addr),
        units=units,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", name="k8s_juju")
def k8s_juju_fixture(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Temporary K8s model — uses jubilant only for model lifecycle."""
    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models, controller=MICROK8S_CONTROLLER_NAME) as juju:
        yield juju


@pytest.fixture(scope="module", name="k8s_model")
def k8s_model_fixture(k8s_juju: jubilant.Juju) -> str:
    """K8s model name in ``controller:model`` format for subprocess calls."""
    return k8s_juju.model


@pytest.fixture(scope="module", name="prometheus_app")
def prometheus_app_fixture(k8s_model: str) -> AppInfo:
    """Deploy prometheus-k8s via subprocess."""
    _juju_cli("deploy", "prometheus-k8s", "--channel", "1/stable", model=k8s_model)
    status = _wait_for_status(k8s_model, lambda s: _all_active(s, "prometheus-k8s"))
    k8s_model_name = k8s_model.split(":", 1)[1]
    _juju_cli(
        "offer",
        f"{k8s_model_name}.prometheus-k8s:receive-remote-write",
        "-c",
        MICROK8S_CONTROLLER_NAME,
    )
    return _app_info_from_status(status, "prometheus-k8s")


@pytest.fixture(scope="module", name="grafana_app")
def grafana_app_fixture(k8s_model: str, prometheus_app: AppInfo) -> AppInfo:
    """Deploy grafana-k8s via subprocess."""
    _juju_cli("deploy", "grafana-k8s", "--channel", "1/stable", model=k8s_model)
    _juju_cli(
        "integrate",
        "grafana-k8s:grafana-source",
        f"{prometheus_app.charm_name}:grafana-source",
        model=k8s_model,
    )
    status = _wait_for_status(k8s_model, lambda s: _all_active(s, "grafana-k8s", "prometheus-k8s"))
    k8s_model_name = k8s_model.split(":", 1)[1]
    _juju_cli(
        "offer",
        f"{k8s_model_name}.grafana-k8s:grafana-dashboard",
        "-c",
        MICROK8S_CONTROLLER_NAME,
    )
    return _app_info_from_status(status, "grafana-k8s")


@pytest.fixture(scope="module", name="traefik_ingress")
def traefik_ingress_fixture(k8s_model: str, prometheus_app: AppInfo, grafana_app: AppInfo) -> None:
    """Deploy traefik ingress via subprocess."""
    _juju_cli("deploy", "traefik-k8s", "--channel", "latest/stable", model=k8s_model)
    _juju_cli("integrate", "traefik-k8s", f"{prometheus_app.charm_name}:ingress", model=k8s_model)
    _juju_cli("integrate", "traefik-k8s", f"{grafana_app.charm_name}:ingress", model=k8s_model)


@pytest.fixture(scope="module", name="grafana_password")
def grafana_password_fixture(k8s_model: str, grafana_app: AppInfo) -> str:
    """Get Grafana admin password via juju run."""
    unit = next(iter(grafana_app.units.keys()))
    result = _juju_cli("run", unit, "get-admin-password", "--format", "json", model=k8s_model)
    data = json.loads(result.stdout)
    return data[unit]["results"]["admin-password"]


@pytest.fixture(scope="module", name="openstack_app_cos_agent")
def openstack_app_cos_agent_fixture(
    juju: jubilant.Juju, app_openstack_runner: Application
) -> Application:
    """Deploy cos-agent via subprocess; return libjuju Application for async ops."""
    os_model = juju.model
    _juju_cli(
        "deploy",
        COS_AGENT_CHARM,
        "--channel",
        "2/candidate",
        "--base",
        "ubuntu@22.04",
        "--revision",
        "149",
        model=os_model,
    )
    _juju_cli("integrate", app_openstack_runner.name, COS_AGENT_CHARM, model=os_model)
    _wait_for_status(
        os_model,
        lambda s: _all_agents_idle(s, app_openstack_runner.name, COS_AGENT_CHARM),
    )
    return app_openstack_runner


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("traefik_ingress")
@pytest.mark.openstack
async def test_prometheus_metrics_subprocess(
    juju: jubilant.Juju,
    k8s_model: str,
    openstack_app_cos_agent: Application,
    grafana_app: AppInfo,
    grafana_password: str,
    prometheus_app: AppInfo,
    test_github_branch: Branch,
    github_repository: Repository,
    instance_helper: OpenStackInstanceHelper,
):
    """Subprocess variant of test_prometheus_metrics.

    arrange: given a prometheus charm application.
    act: when GitHub runner is integrated.
    assert: the datasource is registered and basic metrics are available.
    """
    os_model = juju.model
    k8s_model_name = k8s_model.split(":", 1)[1]
    _juju_cli(
        "consume",
        f"{MICROK8S_CONTROLLER_NAME}:{k8s_model_name}.prometheus-k8s",
        "prometheus-k8s",
        model=os_model,
    )
    _juju_cli(
        "consume",
        f"{MICROK8S_CONTROLLER_NAME}:{k8s_model_name}.grafana-k8s",
        "grafana-k8s",
        model=os_model,
    )

    _juju_cli("integrate", COS_AGENT_CHARM, "prometheus-k8s", model=os_model)
    _juju_cli("integrate", COS_AGENT_CHARM, "grafana-k8s", model=os_model)
    _wait_for_status(
        os_model,
        lambda s: _all_agents_idle(s, openstack_app_cos_agent.name, COS_AGENT_CHARM),
    )

    grafana_ip = grafana_app.units["grafana-k8s/0"].address
    _patiently_wait_for_prometheus_datasource(
        grafana_ip=grafana_ip, grafana_password=grafana_password
    )

    await instance_helper.ensure_charm_has_runner(openstack_app_cos_agent)
    await dispatch_workflow(
        app=openstack_app_cos_agent,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )
    # Set the number of virtual machines to 0 to speedup reconciliation
    await openstack_app_cos_agent.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})

    async def _no_runners() -> bool:
        """Check that no runners are active."""
        action = await openstack_app_cos_agent.units[0].run_action("check-runners")
        await action.wait()
        return (
            action.status == "completed"
            and action.results["online"] == "0"
            and action.results["offline"] == "0"
            and action.results["unknown"] == "0"
        )

    await wait_for(_no_runners, timeout=10 * 60, check_interval=10)

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
