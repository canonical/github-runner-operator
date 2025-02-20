#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Helper functions for integration tests."""

import subprocess
from time import sleep

import requests

GITHUB_RUNNER_MANAGER_ADDRESS = "127.0.0.1:8080"


def get_lock_status() -> str:
    """Get the status of the lock.

    Returns:
        str: The status of the lock.
    """
    response = requests.get(f"http://{GITHUB_RUNNER_MANAGER_ADDRESS}/lock/status")
    return response.content.decode("utf-8")


def acquire_lock():
    """Acquire the lock."""
    requests.get(f"http://{GITHUB_RUNNER_MANAGER_ADDRESS}/lock/acquire")


def release_lock():
    """Release the lock."""
    requests.get(f"http://{GITHUB_RUNNER_MANAGER_ADDRESS}/lock/release")


def wait_for_reconcile():
    """Wait for reconcile service to run.

    The reconcile service is not yet implemented.
    Sleep to let the reconcile run the logging of lock status every 10 secs.
    """
    sleep(15)


def get_app_log(app: subprocess.Popen) -> str:
    """Get the log from the github-runner-manager application.

    The log includes both the reconcile service and the HTTP server.

    Args:
        app: The process running the app.

    Returns:
        The logs.
    """
    assert app.stderr is not None, "Test setup failure: Missing stderr stream"
    return app.stderr.read().decode("utf-8")
