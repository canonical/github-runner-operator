# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import pytest
from ops.model import ActiveStatus, Application, BlockedStatus
from pytest_operator.plugin import OpsTest


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_missing_config(ops_test: OpsTest, app: Application) -> None:
    """
    arrange: Deploy an application without token configuration
    act: Check the status the application
    assert: The application is in blocked status.
    """
    await ops_test.model.wait_for_idle()
    assert ops_test.model.applications["github-runner"].status == BlockedStatus.name


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_config(ops_test: OpsTest, app: Application, token: str) -> None:
    """
    arrange: Deploy an application without token configuration
    act: Set the token configuration and wait.
    assert: The application is in active status.
    """
    await app.set_config({"token": token})
    await ops_test.model.wait_for_idle()
    assert ops_test.model.applications["github-runner"].status == ActiveStatus.name
