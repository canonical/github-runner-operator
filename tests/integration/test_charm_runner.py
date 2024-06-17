# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model

from charm_state import (
    RUNNER_STORAGE_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    VM_CPU_CONFIG_NAME,
    VM_DISK_CONFIG_NAME,
    VM_MEMORY_CONFIG_NAME,
    InstanceType,
)
from tests.integration.helpers import openstack, lxd
from tests.status_name import ACTIVE, BLOCKED

@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model,
    basic_app: Application,
    instance_type: InstanceType,
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure the charm has one runner before starting a test.
    """
    if instance_type == InstanceType.LOCAL_LXD:
        await lxd.ensure_charm_has_runner(basic_app, model)
    if instance_type == InstanceType.OPENSTACK:
        await openstack.ensure_charm_has_runner(basic_app, model)
    yield basic_app

@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runner(app: Application) -> None:
    """
    arrange: A working application with one runner.
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
async def test_flush_runner_and_resource_config(app: Application, instance_type: InstanceType) -> None:
    """
    arrange: A working application with one runner.
    act:
        1. Run Check_runner action. Record the runner name for later.
        2. Nothing.
        3. Change the virtual machine resource configuration.
        4. Run flush_runner action.

    assert:
        1. One runner exists.
        2. Check the resource matches the configuration.
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
    # Check if the LXD profile is checked by the charm. Only for local LXD.
    configs = await app.get_config()
    if instance_type == InstanceType.LOCAL_LXD:
        await lxd.assert_resource_lxd_profile(unit, configs)
    # OpenStack flavor is not managed by the charm. The charm takes it as a config option.
    # Therefore no need to check it.

    # 3.
    await app.set_config(
        {VM_CPU_CONFIG_NAME: "1", VM_MEMORY_CONFIG_NAME: "3GiB", VM_DISK_CONFIG_NAME: "8GiB"}
    )

    # 4.
    action = await app.units[0].run_action("flush-runners")
    await action.wait()

    configs = await app.get_config()
    if instance_type == InstanceType.LOCAL_LXD:
        await lxd.assert_resource_lxd_profile(unit, configs)
        await lxd.wait_till_num_of_runners(unit, 1)
    if instance_type == InstanceType.OPENSTACK:
        await openstack.wait_till_num_of_runners(unit, 1)

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
async def test_token_config_changed_insufficient_perms(
    model: Model, app: Application, token: str, instance_type: InstanceType
) -> None:
    """
    arrange: A working application with one runner.
    act: Change the token to be invalid and set the number of runners to zero.
    assert: The active runner should be removed, regardless of the invalid new token.
    """
    unit = app.units[0]

    await app.set_config({TOKEN_CONFIG_NAME: "invalid-token", VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await model.wait_for_idle()

    if instance_type == InstanceType.LOCAL_LXD:
        await lxd.wait_till_num_of_runners(unit, 1)
    if instance_type == InstanceType.OPENSTACK:
        await openstack.wait_till_num_of_runners(unit, 1)