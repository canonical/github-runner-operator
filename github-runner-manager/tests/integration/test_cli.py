#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration test for github-runner-manager cli."""

import subprocess
from time import sleep

from tests.integration.helper import get_app_log, health_check


def test_app_reconcile(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Check the state of the lock over time.
    assert: The reconcile service should run and acquire the lock at some point.
    """
    sleep(15)
    app.terminate()
    logs = get_app_log(app)
    assert "Starting the server..." in logs
    assert "Staring the reconcile_service..." in logs


def test_app_http_server(web_started_app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Make health check HTTP request.
    assert: The health check should succeed.
    """
    health_check()
