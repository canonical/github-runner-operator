# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import json

import pytest
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus, BlockedStatus

from runner import Runner
from utilities import retry


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency()
async def test_missing_config(model: Model, app: Application) -> None:
    """
    arrange: Deploy an application without token configuration.
    act: Check the status the application.
    assert: The application is in blocked status.
    """
    await model.wait_for_idle()
    # mypy can not find type of `name` attribute.
    assert app.status == BlockedStatus.name  # type: ignore
    assert app.units[0].workload_status == BlockedStatus.name  # type: ignore
    assert (
        app.units[0].workload_status_message == "Missing required charm configuration: ['token']"
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_missing_config"])
async def test_config(model: Model, app: Application, token_one: str) -> None:
    """
    arrange: Deploy an application without token configuration.
    act: Set the token configuration and wait.
    assert: The application is in active status.
    """
    await app.set_config({"token": token_one})
    await model.wait_for_idle()

    action = await app.units[0].run_action("update-runner-bin")
    await action.wait()
    await model.wait_for_idle()

    # mypy can not find type of `name` attribute.
    assert app.status == ActiveStatus.name  # type: ignore


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_config"])
async def test_check_runners_with_no_runner(model: Model, app: Application) -> None:
    """
    arrange: An working application of github-runner with no runners.
    act: Run check-runners action.
    assert: Action returns with no runners.
    """
    await model.wait_for_idle()
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
    assert not action.results["runners"]


@retry(tries=30, delay=30)
async def check_runner_instance(app: Application, num: int) -> None:
    """Helper function to wait for runner instances to be ready.

    Args:
      app: Application instance to check the runners.
      num: Number of runner instances to check for.
    """
    action = await app.units[0].run("lxc list --format json")
    await action.wait()

    assert action.results["return-code"] == 0

    lxc_instance = json.loads(action.results["stdout"])
    assert len(lxc_instance) == num

    for instance in lxc_instance:
        action = await app.units[0].run(f"lxc exec {instance['name']} -- ps aux")
        await action.wait()

        assert f"/bin/bash {Runner.runner_script}" in action.results["stdout"]


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_check_runners_with_no_runner"])
async def test_reconcile_runners_spawn_one(model: Model, app: Application) -> None:
    """
    arrange: An working application of github-runner with no runners.
    act: Set number of runner to 1, and run reconcile-runners.
    assert: One runner instance exists.
    """
    await app.set_config({"virtual-machines": "1"})
    action = await app.units[0].run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle()

    await check_runner_instance(app, 1)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_reconcile_runners_spawn_one"])
async def test_check_runners(model: Model, app: Application, app_name: str) -> None:
    """
    arrange: An working application of github-runner with one runner.
    act: Run check-runners action.
    assert: Action returns with one runner.
    """
    await model.wait_for_idle()
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    runner_names = action.results["runners"].split(", ")
    assert len(runner_names) == 1
    assert runner_names[0].startswith(f"{app_name}-0")


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_check_runners"])
async def test_change_token(model: Model, app: Application, token_two: str) -> None:
    """
    arrange: An working application of github-runner with one runner.
    act: Change the token in charm configuration.
    assert: Existing runners are flushed, and repo-policy-compliance is using the new token.
    """
    await app.set_config({"token": token_two})
    await model.wait_for_idle()

    # The old runner should be flushed out.
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    action = await app.units[0].run("cat /etc/systemd/system/repo-policy-compliance.service")
    await action.wait()

    assert f"GITHUB-TOKEN={token_two}" in action.results["stdout"]
