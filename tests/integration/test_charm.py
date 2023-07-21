# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import json
import pytest
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus, BlockedStatus
from pytest_operator.plugin import OpsTest


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
async def test_config(model: Model, app: Application, token: str) -> None:
    """
    arrange: Deploy an application without token configuration.
    act: Set the token configuration and wait.
    assert: The application is in active status.
    """
    await app.set_config({"token": token})
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


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_check_runners_with_no_runner"])
async def test_spawn_runner(model: Model, app: Application, path: str, token: str) -> None:
    await app.set_config({"virtual-machines": "1"})
    await model.wait_for_idle()

    action = await app.units[0].run("lxc list --format json")
    await action.wait()

    assert action.results["return_code"] == 0

    lxc_instance = json.loads(action.results["output"])
    assert len(lxc_instance) == 1


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.dependency(depends=["test_spawn_runner"])
async def test_check_runners_with_no_runner(ops_test: OpsTest, app: Application) -> None:
    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    runner_names = action.results["runners"].split(", ")
    assert len(runner_names) == 1
    assert runner_names[0].start_with("github-runner-0-")
