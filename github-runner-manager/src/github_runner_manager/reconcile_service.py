# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import logging
from threading import Lock
from time import sleep

from github_runner_manager.cli_config import Configuration

logger = logging.getLogger(__name__)


def start_reconcile_service(_: Configuration, lock: Lock) -> None:
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    # The reconcile service is not implemented yet, current logging the lock status.
    while True:
        logger.info("Lock locked: %s", lock.locked())
        logger.info("Attempting to acquire lock for reconcile...")
        with lock:
            logger.info("Reconciling the runners...")
            sleep(10)
        logger.info("Reconcile of runners completed")
