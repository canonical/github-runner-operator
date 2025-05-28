# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import getpass
import grp
import logging
import os
from pathlib import Path
from threading import Lock
from time import sleep
import uuid

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import UserInfo
from github_runner_manager.manager.runner_scaler import RunnerScaler

logger = logging.getLogger(__name__)

RECONCILE_ID_FILE = Path("/var/log/reconcile.id")

RECONCILE_SERVICE_START_MSG = "Starting the reconcile service..."
RECONCILE_START_MSG = "Start reconciliation"
RECONCILE_END_MSG = "End reconciliation"


def get_runner_scaler(app_config: ApplicationConfiguration) -> RunnerScaler:
    """Get runner scaler.

    Args:
        app_config: The configuration of github-runner-manager.

    Returns:
        The RunnerScaler object.
    """
    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()))
    return RunnerScaler.build(app_config, user)


def start_reconcile_service(app_config: ApplicationConfiguration, lock: Lock) -> None:
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    logger.info(RECONCILE_SERVICE_START_MSG)
    
    # This is used for in test to distinguish which reconcile run the unit is at.
    RECONCILE_ID_FILE.write_text(uuid.uuid4())

    while True:
        with lock:
            logger.info(RECONCILE_START_MSG)
            runner_scaler = get_runner_scaler(app_config)
            delta = runner_scaler.reconcile()
            logger.info("Change in number of runner after reconcile: %s", delta)
        logger.info(RECONCILE_END_MSG)
        RECONCILE_ID_FILE.write_text(uuid.uuid4())
        
        sleep(app_config.reconcile_interval * 60)
