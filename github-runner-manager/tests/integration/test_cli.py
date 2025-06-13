#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration test for github-runner-manager cli."""

import logging
import subprocess

from github_runner_manager.reconcile_service import RECONCILE_SERVICE_START_MSG
from tests.integration.helper import get_app_log, health_check

logger = logging.getLogger(__name__)


def test_app_reconcile(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Check the state of the lock over time.
    assert: The reconcile service should run and acquire the lock at some point.
    """
    logger.info("Terminating the application...")
    app.terminate()
    logger.info("Getting the logs...")
    logs = get_app_log(app)
    assert "Starting the server..." in logs
    assert RECONCILE_SERVICE_START_MSG in logs


def test_app_http_server(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Make health check HTTP request.
    assert: The health check should succeed.
    """
    health_check()
