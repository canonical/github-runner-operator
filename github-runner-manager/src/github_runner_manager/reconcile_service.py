# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import getpass
import grp
import logging
import os
import uuid
from pathlib import Path
from threading import Lock
from time import sleep

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import UserInfo
from github_runner_manager.manager.runner_scaler import RunnerScaler

logger = logging.getLogger(__name__)

RECONCILE_ID_FILE = Path("~").expanduser() / "reconcile.id"
RECONCILE_SERVICE_START_MSG = "Starting the reconcile service..."
RECONCILE_START_MSG = "Start reconciliation"
RECONCILE_END_MSG = "End reconciliation"


def get_runner_scaler(
    app_config: ApplicationConfiguration, python_path: str | None = None
) -> RunnerScaler:
    """Get runner scaler.

    Args:
        app_config: The configuration of github-runner-manager.
        python_path: The PYTHONPATH to access the github-runner-manager library.

    Returns:
        The RunnerScaler object.
    """
    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)
    return RunnerScaler.build(app_config, user, python_path)


def start_reconcile_service(
    app_config: ApplicationConfiguration, python_path: str | None, lock: Lock
) -> None:
    """Start the reconcile server.

    Args:
        app_config: The configuration of the application.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        lock: The lock representing modification access to the managed set of runners.
    """
    logger.info(RECONCILE_SERVICE_START_MSG)

    # This is used for in test to distinguish which reconcile run the unit is at.
    RECONCILE_ID_FILE.write_text(str(uuid.uuid4()), encoding="utf-8")

    while True:
        with lock:
            logger.info(RECONCILE_START_MSG)
            runner_scaler = get_runner_scaler(app_config, python_path=python_path)
            delta = runner_scaler.reconcile()
            logger.info("Change in number of runner after reconcile: %s", delta)
        logger.info(RECONCILE_END_MSG)
        RECONCILE_ID_FILE.write_text(str(uuid.uuid4()), encoding="utf-8")

        sleep(app_config.reconcile_interval * 60)
