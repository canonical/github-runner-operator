# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""


import pytest
from juju.application import Application
from juju.model import Model

from runner_manager import RunnerManager
from tests.integration.helpers import (
    check_resource_config,
    check_runner_instance,
    remove_runner_bin,
)
from tests.status_name import ACTIVE_STATUS_NAME, BLOCK_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_missing_config(app_no_token: Application) -> None:
    """
    arrange: An application without token configuration.
    act: Check the status the application.
    assert: The application is in blocked status.
    """
    assert app_no_token.status == BLOCK_STATUS_NAME

    unit = app_no_token.units[0]
    assert unit.workload_status == BLOCK_STATUS_NAME
    assert unit.workload_status_message == "Missing required charm configuration: ['token']"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_config(model: Model, app: Application, app_name: str, token_alt: str) -> None:
    """
    arrange: An working application with no runners.
    act:
        1. Nothing
        2. Run update-runner-bin action.
        3. Run check-runners action.
        4. Configure to one runner and run reconcile-runners action.
        5. Run check-runners action.
        6. Change the virtual machine resource configuration.
        7. Run flush-runners action.
        8. Change the token configuration.
    assert:
        1. The application is in active status.
        2. Runner binary exists in the charm.
        3. Action returns result with no runner.
        4. a. One runner should be spawned.
           b. LXD profile matching the default virtual machine resources exists.
        5. Action returns result with one runner.
        6. Nothing.
        7. a. One runner should exist. The runner name should be different.
           b. LXD profile matching virtual machine resources of step 6 exists.
        8. a. The repo-policy-compliance using the new token.
           b. Current runners should be flushed out.
    """
    unit = app.units[0]

    # 1.
    assert app.status == ACTIVE_STATUS_NAME

    # 2.
    # Ensure there is no runner binary.
    await remove_runner_bin(unit)

    action = await unit.run_action("update-runner-bin")
    await action.wait()

    await model.wait_for_idle()

    assert app.status == ACTIVE_STATUS_NAME
    action = await unit.run(f"test -f {RunnerManager.runner_bin_path}")
    await action.wait()
    assert action.results["return-code"] == 0

    # 3.
    # Verify there is no runners.
    await check_runner_instance(unit, 0)

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
    assert not action.results["runners"]

    # 4.
    await app.set_config({"virtual-machines": "1"})

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle()

    configs = await app.get_config()
    await check_resource_config(unit, configs)
    await check_runner_instance(unit, 1)

    # 5.
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    runner_names = action.results["runners"].split(", ")
    assert len(runner_names) == 1
    assert runner_names[0].startswith(f"{app_name}-0")

    # 6.
    await app.set_config({"vm-cpu": 1, "vm-memory": "3GiB", "vm-disk": "5GiB"})

    # 7.
    action = await app.units[0].run_action("flush-runners")
    await action.wait()

    configs = await app.get_config()
    await check_resource_config(unit, configs)
    await check_runner_instance(unit, 1)

    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    new_runner_names = action.results["runners"].split(", ")
    assert len(new_runner_names) == 1
    assert new_runner_names[0] != runner_names[0]

    # 8.
    await app.set_config({"token": token_alt})
    await model.wait_for_idle()

    # The old runner should be flushed out.
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    action = await app.units[0].run("cat /etc/systemd/system/repo-policy-compliance.service")
    await action.wait()

    assert action.status == "completed"
    assert f"GITHUB_TOKEN={token_alt}" in action.results["stdout"]

    # Cleanup
    await app.set_config({"virtual-machines": 0})
