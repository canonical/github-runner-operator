#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to pull and remove the logs of the crashed runners."""

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from runner import Runner

CRASHED_RUNNER_LOGS_DIR_PATH = Path("/var/log/github-runner-crashed")
DIAG_DIR_PATH = Path("/home/ubuntu/github-runner/_diag")
SYSLOG_PATH = Path("/var/log/syslog")

OUTDATED_LOGS_IN_SECONDS = 7 * 24 * 60 * 60

logger = logging.getLogger(__name__)


def get_crashed(runner: Runner) -> None:
    """Pull the logs of the crashed runner and put them in a directory named after the runner.

    Expects the runner to have an instance.

    Args:
        runner: The runner.
    """
    logger.info("Pulling the logs of the crashed runner %s.", runner.config.name)
    if runner.instance is None:
        logger.error(
            "Cannot pull the logs for %s as runner has no running instance.", runner.config.name
        )
        return

    target_log_path = CRASHED_RUNNER_LOGS_DIR_PATH / runner.config.name
    target_log_path.mkdir(parents=True, exist_ok=True)

    runner.instance.files.pull_file(str(DIAG_DIR_PATH), str(target_log_path), is_dir=True)
    runner.instance.files.pull_file(str(SYSLOG_PATH), str(target_log_path))


def remove_outdated_crashed() -> None:
    """Remove the logs of the crashed runners that are too old."""
    maxage_absolute = time.time() - OUTDATED_LOGS_IN_SECONDS
    dt_object = datetime.fromtimestamp(maxage_absolute)
    logger.info(
        "Removing the outdated logs of the crashed runners. "
        "All logs older than %s will be removed.",
        dt_object.strftime("%Y-%m-%d %H:%M:%S"),
    )

    for log_path in CRASHED_RUNNER_LOGS_DIR_PATH.glob("*"):
        if log_path.is_dir() and (log_path.stat().st_mtime < maxage_absolute):
            logger.info("Removing the outdated logs of the crashed runner %s.", log_path.name)
            try:
                shutil.rmtree(log_path)
            except OSError:
                logger.exception(
                    "Unable to remove the outdated logs of the crashed runner %s.", log_path.name
                )
