#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

from juju.application import Application
from juju.model import Model

from tests.integration.helpers import ensure_charm_has_runner


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
    assert action.results["runners"] == "[]"


async def test_openstack_reconcile_one_runner(
    model: Model,
    app_openstack_runner: Application,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act: Change number of runners to one and reconcile.
    assert: One runner is spawned.
    """
    ensure_charm_has_runner(app_openstack_runner, model)
