# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import pytest
from ops.model import ActiveStatus, BlockedStatus
from juju.model import Model
from juju.application import Application
from pytest_operator.plugin import OpsTest


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_missing_config(model: Model, app: Application) -> None:
    """
    arrange: Deploy an application without token configuration.
    act: Check the status the application.
    assert: The application is in blocked status.
    """
    await model.wait_for_idle()
    assert app.status == BlockedStatus.name
    assert app.status_message == ""


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_config(model: Model, app: Application, token: str) -> None:
    """
    arrange: Deploy an application without token configuration.
    act: Set the token configuration and wait.
    assert: The application is in active status.
    """
    await app.set_config({"token": token})
    await model.wait_for_idle()
    assert app.status == ActiveStatus.name


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runners(ops_test: OpsTest, app: Application) -> None:
    """
    arrange: An working application of github-runner.
    act: Run check-runners action.
    assert: The returned runner status is correct.
    """
    action = app.units[0].run_action("check-runners")
    result = await action.wait()
    print(result)
