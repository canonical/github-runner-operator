#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

from juju.application import Application
from juju.model import Model

from tests.integration.helpers import set_app_runner_amount


async def test_openstack_check_runner(
    app_openstack_runner: Application,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act: Run check-runners action.
    assert: No runners exists.
    """
    unit = app_openstack_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"


async def test_openstack_reconcile_one_runner(
    model: Model,
    app_openstack_runner: Application,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act:
        1. Change number of runners to one and reconcile.
        2. Run check-runners action.
        3. Change number of runners to zero.
    assert:
        1. One runner is spawned.
        2. One online runner.
        3. No runners.
    """
    unit = app_openstack_runner.units[0]

    # 1.
    # The function sets charm config to one runner and runs reconcile action.
    # Waits until one runner is spawned.
    await set_app_runner_amount(app_openstack_runner, model, 1)

    # 2.
    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    await set_app_runner_amount(app_openstack_runner, model, 0)
