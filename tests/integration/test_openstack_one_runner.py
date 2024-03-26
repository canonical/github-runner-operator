#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

import pytest
from juju.application import Application
from juju.model import Model

from tests.status_name import ACTIVE


async def test_openstack_check_runner(
    model: Model,
    app_openstack_runner: Application,
):
    """
    arrange:
    act:
    assert:
    """
    pytest.set_trace()
    await model.wait_for_idle(apps=[app_openstack_runner.name], status=ACTIVE, timeout=40 * 60)
    unit = app_openstack_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
