#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to pull and remove the logs of the crashed runners."""

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

RUNNER_LOGS_DIR_PATH = Path("/var/log/github-runner-logs")

SYSLOG_PATH = Path("/var/log/syslog")

OUTDATED_LOGS_IN_SECONDS = 7 * 24 * 60 * 60

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


def remove_outdated() -> None:
    """Remove the logs that are too old."""
    maxage_absolute = time.time() - OUTDATED_LOGS_IN_SECONDS
    dt_object = datetime.fromtimestamp(maxage_absolute)
    logger.info(
        "Removing the outdated logs of the crashed runners. "
        "All logs older than %s will be removed.",
        dt_object.strftime("%Y-%m-%d %H:%M:%S"),
    )

    for log_path in RUNNER_LOGS_DIR_PATH.glob("*"):
        if log_path.is_dir() and (log_path.stat().st_mtime < maxage_absolute):
            logger.info("Removing the outdated logs of the runner %s.", log_path.name)
            try:
                shutil.rmtree(log_path)
            except OSError:
                logger.exception(
                    "Unable to remove the outdated logs of the runner %s.", log_path.name
                )
