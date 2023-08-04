# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm."""

import pytest
from juju.application import Application

from tests.status_name import BLOCKED_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_missing_config(app_no_token: Application) -> None:
    """
    arrange: An application without token configuration.
    act: Check the status the application.
    assert: The application is in blocked status.
    """
    assert app_no_token.status == BLOCKED_STATUS_NAME

    unit = app_no_token.units[0]
    assert unit.workload_status == BLOCKED_STATUS_NAME
    assert unit.workload_status_message == "Missing required charm configuration: ['token']"
