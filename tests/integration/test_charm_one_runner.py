# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

from datetime import datetime, timezone
from time import sleep

import github
import pytest
import requests
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm import GithubRunnerCharm
from github_client import GithubClient
from tests.integration.helpers import (
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    assert_resource_lxd_profile,
    get_runner_names,
    reconcile,
    run_in_lxd_instance,
    run_in_unit,
    start_test_http_server,
    wait_till_num_of_runners,
)
from tests.status_name import ACTIVE, BLOCKED


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
async def test_wait_on_busy_runner_repo_check(
    app_runner: Application,
    github_repository: Repository,
    runner_manager_github_client: GithubClient,
) -> None:
    """
    arrange: A working application with one runner.
    act:
        1. Dispatch a workflow that wait for 30 mins.
        2. Run flush-runners action.
    assert:
        1. The runner is is busy status.
        2.  a. The flush-runners action should take less than the timeout.
            b. The runner should be flushed.

    """
    unit = app_runner.units[0]

    names = await get_runner_names(unit)
    assert len(names) == 1

    runner_to_be_used = names[0]

    # 1.
    main_branch = github_repository.get_branch(github_repository.default_branch)
    workflow = github_repository.get_workflow(id_or_file_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME)

    workflow.create_dispatch(main_branch, {"runner": app_runner.name, "minutes": 30})

    # Wait until runner is busy.
    for _ in range(30):
        all_runners = runner_manager_github_client.get_runner_github_info(
            f"{github_repository.owner}/{github_repository.name}"
        )
        runners = [runner for runner in all_runners if runner.name == runner_to_be_used]
        assert len(runners) == 1, "Should not occur as GitHub enforce unique naming of runner"
        runner = runners[0]
        if runner["busy"]:
            start_time = datetime.now(timezone.utc)
            break

        sleep(10)
    else:
        assert False, "Timeout while waiting for workflow to complete"

    # 2.
    action = await unit.run_action("flush-runners")
    await action.wait()

    end_time = datetime.now(timezone.utc)

    # The `RunnerManager` class `flush` method has a timeout of 5 * 30.
    diff = end_time - start_time
    assert diff.total_seconds() < 5 * 30

    names = await get_runner_names(unit)
    assert len(names) == 0


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
