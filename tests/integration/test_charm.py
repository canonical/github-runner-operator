# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

from asyncio import sleep

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    assert_resource_lxd_profile,
    assesrt_num_of_runners,
    get_runner_names,
)
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_interval(model: Model, app: Application) -> None:
    """
    arrange: An working application with one runner.
    act:
        1. Crash the one runner
        2. Wait for 2 minutes.
    assert:
        1. No runner exists.
        2. One runner exists.
    """
    unit = app.units[0]
    await assesrt_num_of_runners(unit, 1)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]
    action = await unit.run(f"lxc stop --force {runner_name}")
    await action.wait()
    await assesrt_num_of_runners(unit, 0)

    await sleep(2 * 60)
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    await assesrt_num_of_runners(unit, 1)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_flush_runner_and_resource_config(app: Application) -> None:
    """
    arrange: An working application with one runner.
    act:
        1. Run Check_runner action. Record the runner name for later.
        2. Nothing.
        3. Change the virtual machine resource configuration.
        4. Run flush_runner action.

    assert:
        1. One runner exists.
        2. LXD profile of matching resource config exists.
        3. Nothing.
        4.  a. The runner name should be different to the runner prior running
                the action.
            b. LXD profile matching virtual machine resources of step 2 exists.

    Test are combined to reduce number of runner spawned.
    """
    unit = app.units[0]

    # 1.
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    runner_names = action.results["runners"].split(", ")
    assert len(runner_names) == 1

    # 2.
    configs = await app.get_config()
    await assert_resource_lxd_profile(unit, configs)

    # 3.
    await app.set_config({"vm-cpu": "1", "vm-memory": "3GiB", "vm-disk": "5GiB"})

    # 4.
    action = await app.units[0].run_action("flush-runners")
    await action.wait()

    configs = await app.get_config()
    await assert_resource_lxd_profile(unit, configs)
    await assesrt_num_of_runners(unit, 1)

    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    new_runner_names = action.results["runners"].split(", ")
    assert len(new_runner_names) == 1
    assert new_runner_names[0] != runner_names[0]


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runner(app: Application) -> None:
    """
    arrange: An working application with one runner.
    act: Run check_runner action.
    assert: Action returns result with one runner.
    """
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_token_config_changed(model: Model, app: Application, token_alt: str) -> None:
    """
    arrange: An working application with one runner.
    act: Change the token configuration.
    assert: The repo-policy-compliance using the new token.
    """
    await app.set_config({"token": token_alt})
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    action = await app.units[0].run("cat /etc/systemd/system/repo-policy-compliance.service")
    await action.wait()

    assert action.status == "completed"
    assert f"GITHUB_TOKEN={token_alt}" in action.results["stdout"]
