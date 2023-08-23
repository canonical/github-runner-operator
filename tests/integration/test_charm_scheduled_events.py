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

from tests.integration.helpers import get_runner_names, run_in_unit, wait_till_num_of_runners
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_interval(model: Model, app_scheduled_events: Application) -> None:
    """
    arrange: An working application with one runner.
    act:
        1. Crash the one runner
        2. Wait for 3 minutes, and then wait for ActiveStatus.
    assert:
        1. No runner exists.
        2. One runner exists. The runner name should not be the same as the starting one.
    """
    unit = app_scheduled_events.units[0]

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]
    await run_in_unit(unit, f"lxc stop --force {runner_name}")
    await wait_till_num_of_runners(unit, 0)

    await sleep(3 * 60)
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    assert runner_name != runner_names[0]
