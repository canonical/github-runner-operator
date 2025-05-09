# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import logging
from threading import Lock
from time import sleep

from github_runner_manager.configuration import ApplicationConfiguration

logger = logging.getLogger(__name__)


def start_reconcile_service(_: ApplicationConfiguration, lock: Lock) -> None:
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    logger.info("Staring the reconcile_service...")
    while True:
        with lock:
            logger.info("Acquired the lock for reconciling")
            sleep(10)
        logger.info("Released the lock")
