# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import logging
from threading import Lock
from time import sleep

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.openstack_cloud.configuration import OpenStackConfiguration
from github_runner_manager.manager.runner_scaler import RunnerScaler

logger = logging.getLogger(__name__)


def start_reconcile_service(
    app_config: ApplicationConfiguration, openstack_config: OpenStackConfiguration, lock: Lock
) -> None:
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    _ = RunnerScaler.build(app_config, openstack_config)
    # The reconcile service is not implemented yet, current logging the lock status.
    while True:
        logger.info("Lock locked: %s", lock.locked())
        logger.info("Attempting to acquire lock for reconcile...")
        with lock:
            logger.info("Reconciling the runners...")
            sleep(10)
        logger.info("Reconcile of runners completed")
