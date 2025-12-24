# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import getpass
import grp
import logging
import os
import uuid
from threading import Lock
from time import sleep

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import UserInfo
from github_runner_manager.manager.runner_scaler import RunnerScaler
from github_runner_manager.utilities import get_state_dir

logger = logging.getLogger(__name__)

RECONCILE_SERVICE_START_MSG = "Starting the reconcile service..."
RECONCILE_START_MSG = "Start reconciliation"
RECONCILE_END_MSG = "End reconciliation"


def get_runner_scaler(
    app_config: ApplicationConfiguration,
    python_path: str | None = None,
    base_dir: str | None = None,
) -> RunnerScaler:
    """Get runner scaler.

    Args:
        app_config: The configuration of github-runner-manager.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        base_dir: The base directory for application data.

    Returns:
        The RunnerScaler object.
    """
    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)
    return RunnerScaler.build(app_config, user, python_path, base_dir)


def start_reconcile_service(
    app_config: ApplicationConfiguration,
    python_path: str | None,
    lock: Lock,
    base_dir: str | None = None,
) -> None:
    """Start the reconcile server.

    Args:
        app_config: The configuration of the application.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        lock: The lock representing modification access to the managed set of runners.
        base_dir: The base directory for application data.
    """
    logger.info(RECONCILE_SERVICE_START_MSG)

    # Get the state directory and ensure the reconcile ID file is in it
    resolved_state_dir = get_state_dir(base_dir)
    reconcile_id_file = resolved_state_dir / "reconcile.id"

    # This is used for in test to distinguish which reconcile run the unit is at.
    reconcile_id = uuid.uuid4()
    reconcile_id_file.write_text(str(reconcile_id), encoding="utf-8")

    while True:
        with lock:
            logger.info(RECONCILE_START_MSG)
            logger.info("Reconcile ID: %s", reconcile_id)
            runner_scaler = get_runner_scaler(
                app_config, python_path=python_path, base_dir=base_dir
            )
            delta = runner_scaler.reconcile()
            logger.info("Change in number of runner after reconcile: %s", delta)
        logger.info(RECONCILE_END_MSG)
        reconcile_id = uuid.uuid4()
        reconcile_id_file.write_text(str(reconcile_id), encoding="utf-8")

        sleep(app_config.reconcile_interval * 60)
