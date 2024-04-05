#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

from juju.application import Application
from juju.model import Model

from tests.integration.helpers import reconcile


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
        1. Change number of runners to one and reconcile and run check-runners action.
        3. Change number of runners to zero and run check-runners action.
    assert:
        1. One runner is spawned.
        2. One online runner.
        3. No runners.
    """
    unit = app_openstack_runner.units[0]

    # 1.
    # Waits until one runner is spawned.
    await app_openstack_runner.set_config({"virtual-machines": "1"})
    await reconcile(app=app_openstack_runner, model=model)

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    # 2.
    await app_openstack_runner.set_config({"virtual-machines": "0"})
    await reconcile(app=app_openstack_runner, model=model)

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
