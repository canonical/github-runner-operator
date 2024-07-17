#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to pull and remove the logs of the crashed runners."""

import logging
from pathlib import Path

RUNNER_LOGS_DIR_PATH = Path("/var/log/github-runner-logs")

logger = logging.getLogger(__name__)


def create_logs_dir(runner_name: str) -> Path:
    """Create the directory to store the logs of the crashed runners.

    Args:
        runner_name: The name of the runner.

    Returns:
        The path to the directory where the logs of the crashed runners will be stored.
    """
    target_log_path = RUNNER_LOGS_DIR_PATH / runner_name
    target_log_path.mkdir(parents=True, exist_ok=True)

    return target_log_path
