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

from runner_manager import LXDRunnerManager
from tests.integration.helpers.common import check_runner_binary_exists
from tests.integration.helpers.lxd import get_runner_names, run_in_unit, wait_till_num_of_runners
from tests.status_name import ACTIVE


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_interval(model: Model, app_scheduled_events: Application) -> None:
    """
    arrange: A working application with one runner.
    act:
        1.  a. Remove runner binary.
            b. Crash the one runner
        2.  Wait for 6 minutes, and then wait for ActiveStatus.
    assert:
        1. a. No runner binary exists.
           b. No runner exists.
        2.  a. Runner binary exists.
            b. One runner exists. The runner name should not be the same as the starting one.

    This tests whether the reconcile-runner event is triggered, and updates the dependencies.
    The reconciliation logic is tested with the reconcile-runners action.
    """
    unit = app_scheduled_events.units[0]
    assert await check_runner_binary_exists(unit)

    ret_code, stdout, stderr = await run_in_unit(unit, f"rm -f {LXDRunnerManager.runner_bin_path}")
    assert ret_code == 0, f"Failed to remove runner binary {stdout} {stderr}"
    assert not await check_runner_binary_exists(unit)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]
    ret_code, stdout, stderr = await run_in_unit(unit, f"lxc stop --force {runner_name}")
    assert ret_code == 0, f"Failed to stop lxd instance, {stdout} {stderr}"
    await wait_till_num_of_runners(unit, 0)

    await sleep(10 * 60)
    await model.wait_for_idle(status=ACTIVE, timeout=20 * 60)

    assert await check_runner_binary_exists(unit)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    assert runner_name != runner_names[0]
