#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Helper functions for integration tests."""

import subprocess
from pathlib import Path
from time import sleep
from typing import Sequence

import requests

GITHUB_RUNNER_MANAGER_ADDRESS = "127.0.0.1:8080"
PACKAGE_NAME = "github-runner-manager"


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


def flush_runner(flush_busy: bool):
    """Flush the runners.

    Args:
        flush_busy: Whether to flush busy runners.
    """
    busy = "true" if flush_busy else "false"
    requests.post(
        f"http://{GITHUB_RUNNER_MANAGER_ADDRESS}/runner/flush", headers={"flush-busy": busy}
    )


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


def start_app(config_file: Path, extra_args: Sequence[str]) -> subprocess.Popen:
    """Start the CLI application.

    Args:
        config_file: The Path to the configuration file.
        extra_args: Any extra args to the CLI application.

    Returns:
        The process running the CLI application.
    """
    process = subprocess.Popen(
        [PACKAGE_NAME, "--config-file", config_file, "--debug", *extra_args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stderr is not None, "Test setup failure: Missing stderr stream"
    for line in process.stderr:
        if b"Address already in use" in line:
            assert False, "Test setup failure: Port used for testing taken"
        if b"Press CTRL+C to quit" in line:
            break
    else:
        assert False, "Test setup failure: Abnormal app exit"
    return process


def poll_lock_status(secs: int) -> list[str]:
    """Poll the lock status every second.

    Args:
        secs: How long to poll for in seconds.

    Returns:
        The lock status.
    """
    lock_status = []
    for _ in range(secs):
        lock_status.append(get_lock_status())
        sleep(1)
    return lock_status
