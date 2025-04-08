#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Helper functions for integration tests."""

import subprocess
from pathlib import Path
from typing import Sequence

import requests

GITHUB_RUNNER_MANAGER_ADDRESS = "127.0.0.1:8080"
PACKAGE_NAME = "github-runner-manager"


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
        [
            PACKAGE_NAME,
            "--config-file",
            config_file,
            "--debug",
            *extra_args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stderr is not None, "Test setup failure: Missing stderr stream"
    logs = b""
    for line in process.stderr:
        if b"Address already in use" in line:
            assert False, "Test setup failure: Port used for testing taken"
        if b"Press CTRL+C to quit" in line:
            break
        logs += line
    else:
        assert False, f"Test setup failure: Abnormal app exit with logs:\n{logs.decode('utf-8')}"
    return process


def health_check() -> None:
    """Get health check status."""
    response = requests.get(f"http://{GITHUB_RUNNER_MANAGER_ADDRESS}/health")
    assert response.status_code == 204, "Health check failed"
