# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    assert_resource_lxd_profile,
    get_runner_names,
    run_in_lxd_instance,
    run_in_unit,
    start_test_http_server,
    wait_till_num_of_runners,
)
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_network_access(app: Application) -> None:
    """
    arrange: An working application with one runner. Setup a HTTP server in the juju unit.
    act: Make HTTP call to the HTTP server from inside a runner.
    assert: The HTTP call failed.
    """
    unit = app.units[0]
    port = 4040

    await start_test_http_server(unit, port)

    names = await get_runner_names(unit)
    assert names

    return_code, stdout = await run_in_unit(unit, "lxc network get lxdbr0 ipv4.address")
    assert return_code == 0
    host_ip, _ = stdout.split("/")

    return_code, stdout = await run_in_lxd_instance(
        unit, names[0], f"curl http://{host_ip}:{port}"
    )

    assert return_code != 0
    # TODO: Test stdout as well.
    assert stdout == ""


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
    await wait_till_num_of_runners(unit, 1)

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
    unit = app.units[0]

    await app.set_config({"token": token_alt})
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    return_code, stdout = await run_in_unit(
        unit, "cat /etc/systemd/system/repo-policy-compliance.service"
    )

    assert return_code == 0
    assert stdout is not None
    assert f"GITHUB_TOKEN={token_alt}" in stdout
