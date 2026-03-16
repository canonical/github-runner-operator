# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with no runner."""

import json
import logging

import jubilant
import pytest
from juju.application import Application
from juju.model import Model
from ops import ActiveStatus

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.openstack


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runners_no_runners(app_no_runner: Application) -> None:
    """
    arrange: A working application with no runners.
    act: Run check-runners action.
    assert: Action returns result with no runner.
    """
    unit = app_no_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
    assert action.results["runners"] == "()"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_planner_integration(
    model: Model,
    juju: jubilant.Juju,
    app_no_runner: Application,
    mock_planner_app: Application,
    planner_token_secret_name: str,
) -> None:
    """
    arrange: A working application with no runners and a mock planner, and the secret granted.
    act:
        1. Integrate the application with the mock planner.
        2. Remove the integration.
    assert:
        1. The charm writes its flavor data to the planner relation app data bag.
        2. The charm returns to active status after the relation is removed.
    """
    await model.grant_secret(planner_token_secret_name, app_no_runner.name)
    await model.grant_secret(planner_token_secret_name, mock_planner_app.name)

    await model.relate(f"{app_no_runner.name}:planner", mock_planner_app.name)
    await model.wait_for_idle(
        apps=[app_no_runner.name, mock_planner_app.name],
        status=ActiveStatus.name,
        idle_period=30,
        timeout=10 * 60,
    )

    # Verify the runner charm wrote flavor data to the relation app databag.
    # Query from the planner unit's perspective so "application-data" shows the
    # remote (runner) app's data rather than the planner's own app data.
    planner_unit_name = mock_planner_app.units[0].name
    raw = juju.cli("show-unit", planner_unit_name, "--format", "json")
    unit_data = json.loads(raw)[planner_unit_name]
    planner_rel = next(
        rel
        for rel in unit_data["relation-info"]
        if rel["endpoint"] == "provide-github-runner-planner-v0"
    )
    app_data = planner_rel["application-data"]
    assert app_data["flavor"] == app_no_runner.name
    assert app_data["platform"] == "github"
    assert app_data["priority"] == "50"
    assert app_data["minimum-pressure"] == "0"

    await mock_planner_app.remove_relation(
        "provide-github-runner-planner-v0", f"{app_no_runner.name}:planner"
    )
    await model.wait_for_idle(
        apps=[app_no_runner.name], status=ActiveStatus.name, idle_period=30, timeout=10 * 60
    )
