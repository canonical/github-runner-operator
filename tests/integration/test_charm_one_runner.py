# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model

from charm import GithubRunnerCharm
from tests.integration.helpers import (
    assert_resource_lxd_profile,
    ensure_charm_has_runner,
    get_runner_names,
    reconcile,
    run_in_lxd_instance,
    run_in_unit,
    start_test_http_server,
    wait_till_num_of_runners,
)
from tests.status_name import ACTIVE, BLOCKED


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model,
    app_one_runner: Application,
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure the charm has one runner before starting a test.
    """
    await ensure_charm_has_runner(app_one_runner, model)
    yield app_one_runner


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_network_access(app: Application) -> None:
    """
    arrange: A working application with one runner. Setup a HTTP server in the juju unit.
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
    assert stdout is not None
    host_ip, _ = stdout.split("/", 1)

    return_code, stdout = await run_in_lxd_instance(
        unit, names[0], f"curl http://{host_ip}:{port}"
    )

    assert return_code == 7
    assert stdout is None


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_flush_runner_and_resource_config(app: Application) -> None:
    """
    arrange: A working application with one runner.
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
    await app.set_config({"vm-cpu": "1", "vm-memory": "3GiB", "vm-disk": "8GiB"})

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
async def test_token_config_changed(model: Model, app: Application, token_alt: str) -> None:
    """
    arrange: A working application with one runner.
    act: Change the token configuration.
    assert: The repo-policy-compliance using the new token.
    """
    unit = app.units[0]

    await app.set_config({"token": token_alt})
    await model.wait_for_idle(status=ACTIVE)

    return_code, stdout = await run_in_unit(
        unit, "cat /etc/systemd/system/repo-policy-compliance.service"
    )

    assert return_code == 0
    assert stdout is not None
    assert f"GITHUB_TOKEN={token_alt}" in stdout


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_runners_with_lxd_storage_pool_failure(
    model: Model, app: Application
) -> None:
    """
    arrange: A working application with one runners.
    act:
        1.  a. Set virtual-machines config to 0.
            b. Run reconcile_runners action.
            c. Delete content in the runner LXD storage directory.
        2.  a. Set virtual-machines config to 1.
            b. Run reconcile_runners action.
    assert:
        1. No runner should exist.
        2. One runner should exist.
    """
    unit = app.units[0]

    # 1.
    await app.set_config({"virtual-machines": "0"})

    await reconcile(app=app, model=model)
    await wait_till_num_of_runners(unit, 0)

    exit_code, _ = await run_in_unit(unit, f"rm -rf {GithubRunnerCharm.ram_pool_path}/*")
    assert exit_code == 0

    # 2.
    await app.set_config({"virtual-machines": "1"})

    await reconcile(app=app, model=model)

    await wait_till_num_of_runners(unit, 1)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_change_runner_storage(model: Model, app: Application) -> None:
    """
    arrange: A working application with one runners using memory as disk.
    act:
        1. Change runner-storage to juju-storage.
        2. Change runner-storage back to memory.
    assert:
        1. Application in blocked state.
        2. Application back to active state.
    """
    unit = app.units[0]

    # 1.
    await app.set_config({"runner-storage": "juju-storage"})
    await model.wait_for_idle(status=BLOCKED, timeout=1 * 60)
    assert (
        "runner-storage config cannot be changed after deployment" in unit.workload_status_message
    )

    # 2.
    await app.set_config({"runner-storage": "memory"})
    await model.wait_for_idle(status=ACTIVE, timeout=1 * 60)


async def test_token_config_changed_insufficient_perms(
    model: Model, app: Application, token_alt: str
) -> None:
    """
    arrange: A working application with one runner.
    act: Change the token to be invalid and set the number of runners to zero.
    assert: The active runner should be removed, regardless of the invalid new token.
    """
    unit = app.units[0]

    await app.set_config({"token": "", "virtual-machines": "0"})
    await model.wait_for_idle()

    await wait_till_num_of_runners(unit, num=0)
