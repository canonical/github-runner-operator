# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with scheduled events.

Scheduled events can interfere with most tests. Therefore, an application with
scheduled events are in its own module.
"""

from asyncio import sleep

import pytest
from juju.application import Application
from juju.model import Model

from runner_manager import RunnerManager
from tests.integration.helpers import check_runner_binary_exists, run_in_unit
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_interval(model: Model, app_scheduled_events: Application) -> None:
    """
    arrange: An working application with one runner.
    act:
        1. Remove runner binary.
        2. Wait for 3 minutes.
    assert:
        1. No runner binary exists.
        3. Runner binary exists.

    This tests whether the reconcile-runner event is triggered, and updates the dependencies.
    The reconciliation logic is tested with the reconcile-runners action.
    """
    unit = app_scheduled_events.units[0]
    assert await check_runner_binary_exists(unit)

    await run_in_unit(unit, f"rm -f {RunnerManager.runner_bin_path}")
    assert not await check_runner_binary_exists(unit)

    await sleep(3 * 60)
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    assert await check_runner_binary_exists(unit)
