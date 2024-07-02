# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm import GithubRunnerCharm
from charm_state import RUNNER_STORAGE_CONFIG_NAME, TOKEN_CONFIG_NAME, VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.lxd import (
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

    return_code, stdout, stderr = await run_in_unit(unit, "lxc network get lxdbr0 ipv4.address")
    assert return_code == 0, f"Failed to get network address {stdout} {stderr}"
    assert stdout is not None
    host_ip, _ = stdout.split("/", 1)

    return_code, stdout, _ = await run_in_lxd_instance(
        unit, names[0], f"curl http://{host_ip}:{port}"
    )

    assert return_code == 7
    assert stdout is None


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_token_config_changed(model: Model, app: Application, token_alt: str) -> None:
    """
    arrange: A working application with one runner.
    act: Change the token configuration.
    assert: The repo-policy-compliance using the new token.
    """
    unit = app.units[0]

    await app.set_config({TOKEN_CONFIG_NAME: token_alt})
    await model.wait_for_idle(status=ACTIVE, timeout=30 * 60)

    return_code, stdout, stderr = await run_in_unit(
        unit, "cat /etc/systemd/system/repo-policy-compliance.service"
    )

    assert (
        return_code == 0
    ), f"Failed to get repo-policy-compliance unit file contents {stdout} {stderr}"
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
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})

    await reconcile(app=app, model=model)
    await wait_till_num_of_runners(unit, 0)

    exit_code, stdout, stderr = await run_in_unit(
        unit, f"rm -rf {GithubRunnerCharm.ram_pool_path}/*"
    )
    assert exit_code == 0, f"Failed to delete ram pool {stdout} {stderr}"

    # 2.
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})

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
    await app.set_config({RUNNER_STORAGE_CONFIG_NAME: "juju-storage"})
    await model.wait_for_idle(status=BLOCKED, timeout=1 * 60)
    assert (
        "runner-storage config cannot be changed after deployment" in unit.workload_status_message
    )

    # 2.
    await app.set_config({RUNNER_STORAGE_CONFIG_NAME: "memory"})
    await model.wait_for_idle(status=ACTIVE, timeout=1 * 60)


async def test_runner_labels(
    model: Model, app: Application, github_repository: Repository
) -> None:
    """
    arrange: A working application with one runner.
    act: Change the runner label.
    assert: A runner with the testing label is found.
    """
    unit = app.units[0]

    test_labels = ("label_test", "additional_label", app.name)
    await app.set_config({"labels": f"{test_labels[0]}, {test_labels[1]}"})
    await model.wait_for_idle()

    await wait_till_num_of_runners(unit, num=1)

    found = False
    for runner in github_repository.get_self_hosted_runners():
        runner_labels = tuple(label["name"] for label in runner.labels())
        if all(test_label in runner_labels for test_label in test_labels):
            found = True

    assert found, "Runner with testing label not found."


async def test_disabled_apt_daily_upgrades(model: Model, app: Application) -> None:
    """
    arrange: Given a github runner running on lxd image.
    act: When the runner is spawned.
    assert: No apt related background services are running.
    """
    await model.wait_for_idle()
    unit = app.units[0]
    await wait_till_num_of_runners(unit, num=1)
    names = await get_runner_names(unit)
    assert names, "LXD runners not ready"

    ret_code, stdout, stderr = await run_in_lxd_instance(
        unit, names[0], "sudo systemctl list-units --no-pager"
    )
    assert ret_code == 0, f"Failed to list systemd units {stdout} {stderr}"
    assert stdout, "No units listed in stdout"

    assert "apt-daily" not in stdout  # this also checks for apt-daily-upgrade service
    assert "unattended-upgrades" not in stdout
