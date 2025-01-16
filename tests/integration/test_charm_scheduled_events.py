# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with scheduled events.

Scheduled events can interfere with most tests. Therefore, an application with
scheduled events are in its own module.
"""

from asyncio import sleep

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers.common import InstanceHelper, wait_for
from tests.status_name import ACTIVE

pytestmark = pytest.mark.openstack


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_interval(
    model: Model,
    app_scheduled_events: Application,
    instance_helper: InstanceHelper,
) -> None:
    """
    arrange: A working application with one runner.
    act:
        1.  a. Crash/delete the one runner
        2.  Wait for 6 minutes, and then wait for ActiveStatus.
    assert:
        1. a. No runner exists.
        2. a. One runner exists. The runner name should not be the same as the starting one.

    This tests whether the reconcile-runner event is triggered, and updates the dependencies.
    The reconciliation logic is tested with the reconcile-runners action.
    """
    unit = app_scheduled_events.units[0]

    oldnames = await instance_helper.get_runner_names(unit)
    assert len(oldnames) == 1, "There should be one runner"

    # delete the only runner
    await instance_helper.delete_single_runner(unit)

    async def _no_runners_available() -> bool:
        """Check if there is only one runner."""
        return len(await instance_helper.get_runner_names(unit)) == 0

    await wait_for(_no_runners_available, timeout=30, check_interval=3)

    await sleep(10 * 60)
    await model.wait_for_idle(status=ACTIVE, timeout=20 * 60)

    newnames = await instance_helper.get_runner_names(unit)
    assert len(newnames) == 1, "There should be one runner after reconciliation"
    assert newnames[0] != oldnames[0]
