# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Application-level integration test for planner-driven runner lifecycle.

Tests that PressureReconciler + RunnerManager + OpenStack behave correctly when
planner pressure changes, without requiring a Juju deployment.
"""

import logging
from typing import Iterator

import openstack
import pytest
import yaml

from .application import RunningApplication
from .conftest import wait_for_no_runners, wait_for_runner
from .factories import (
    GitHubConfig,
    OpenStackConfig,
    ProxyConfig,
    TestConfig,
    create_default_config,
)
from .planner_stub import PlannerStub, PlannerStubConfig

logger = logging.getLogger(__name__)


@pytest.fixture
def planner_app(
    tmp_test_dir,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    proxy_config: ProxyConfig | None,
) -> Iterator[tuple[RunningApplication, PlannerStub]]:
    """Start the runner manager application wired to a planner stub at pressure=1.

    Yields:
        Tuple of (RunningApplication, PlannerStub) for use in the test.
    """
    flavor_name = openstack_config.flavor or "small"
    stub = PlannerStub(PlannerStubConfig(initial_pressure=1.0, flavor_name=flavor_name))
    stub.start()
    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        planner_url=stub.base_url,
        planner_token=stub.token,
    )
    # Fire the delete loop every 5 minutes so cleanup is visible within the 15-minute
    # test timeout. The default factory value (60) waits 60 * 60 = 3600 s between ticks.
    # 5 matches the PressureReconcilerConfig default and reflects realistic behavior.
    config["reconcile_interval"] = 5
    config_path = tmp_test_dir / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    log_file_path = test_config.debug_log_dir / f"app-{test_config.test_id}.log"
    app = RunningApplication.create(config_path, log_file_path=log_file_path)
    try:
        yield app, stub
    finally:
        app.stop()
        stub.stop()


def test_planner_pressure_spawns_and_cleans_runner(
    planner_app: tuple[RunningApplication, PlannerStub],
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
) -> None:
    """Planner pressure drives the full runner lifecycle without Juju.

    Arrange: app running in planner mode, stub serving pressure=1.
    Act 1: wait for a runner VM to appear on OpenStack.
    Act 2: set planner pressure to 0.
    Act 3: wait for the runner VM to disappear from OpenStack.
    Assert: runner lifecycle is driven entirely by planner pressure.
    """
    app, stub = planner_app

    runner, _ = wait_for_runner(openstack_connection, test_config, timeout=10 * 60)
    assert runner is not None, "Runner did not appear within timeout"

    stub.set_pressure(0)

    cleaned = wait_for_no_runners(openstack_connection, test_config, timeout=15 * 60)
    assert cleaned, "Runner was not cleaned up after pressure set to 0"
