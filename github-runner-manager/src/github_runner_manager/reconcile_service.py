# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The reconcile service for managing the self-hosted runner."""

import getpass
import grp
import logging
import os
import signal
import sys
import uuid
from pathlib import Path
from threading import Lock
from time import sleep

import openstack
from kombu import Connection

from github_runner_manager.cloud.openstack import OpenStackCloud, OpenStackConfig
from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import UserInfo
from github_runner_manager.manager.reconciler import (
    PrespawnConfig,
    ReactiveConfig,
    ReconcileAlgorithm,
    Reconciler,
    ReconcilerConfig,
)
from github_runner_manager.metrics.metrics import MetricsProvider
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient

logger = logging.getLogger(__name__)

RECONCILE_ID_FILE = Path("~").expanduser() / "reconcile.id"
RECONCILE_SERVICE_START_MSG = "Starting the reconcile service..."
RECONCILE_START_MSG = "Start reconciliation"
RECONCILE_END_MSG = "End reconciliation"

GITHUB_SELF_HOSTED_ARCH_LABELS = {"x64", "arm64"}


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

    openstack_creds = app_config.openstack_configuration.credentials
    system_user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)
    key_dir = Path(f"~{system_user}").expanduser() / ".ssh"

    labels = list(app_config.extra_labels)
    base_quantity = 0
    if combinations := app_config.non_reactive_configuration.combinations:
        combination = combinations[0]
        labels += combination.image.labels
        labels += combination.flavor.labels
        base_quantity = combination.base_virtual_machines
    supported_labels = set(labels) | GITHUB_SELF_HOSTED_ARCH_LABELS

    repo_policy_service = (
        RepoPolicyComplianceClient(
            url=app_config.service_config.repo_policy_compliance.url,
            charm_token=app_config.service_config.repo_policy_compliance.token,
        )
        if app_config.service_config.repo_policy_compliance
        else None
    )
    platform_service = get_platform_service()
    with (
        openstack.connect(
            auth_url=openstack_creds.auth_url,
            project_name=openstack_creds.project_name,
            username=openstack_creds.username,
            password=openstack_creds.password,
            region_name=openstack_creds.region_name,
            user_domain_name=openstack_creds.user_domain_name,
            project_domain_name=openstack_creds.project_domain_name,
        ) as openstack_connection,
        SigtermLoopHandler() as loop_handler,
    ):
        cloud_service = OpenStackCloud(
            connection=openstack_connection,
            config=OpenStackConfig(
                prefix=app_config.openstack_configuration.prefix,
                network=app_config.openstack_configuration.network,
                key_dir=key_dir,
                system_user=system_user.user,
                ingress_tcp_ports=[
                    8080  # change this to be dynamically be alllocated if using jobmanager
                ],
            ),
            service_config=app_config.service_config,
            repo_policy_compliance_service=repo_policy_service,
        )
        reconciler: Reconciler
        algorithm_config: ReactiveConfig | PrespawnConfig
        if app_config.reactive_configuration:
            queue_connection = Connection(app_config.reactive_configuration.queue.mongodb_uri)
            reactive_job_queue = queue_connection.SimpleQueue(
                app_config.reactive_configuration.queue.queue_name
            )
            algorithm_config = ReactiveConfig(
                algorithm=ReconcileAlgorithm.REACTIVE,
                base_quantity=app_config.reactive_configuration.max_total_virtual_machines,
                vm_image=combination.image.name,
                vm_flavor=combination.flavor.name,
                queue=reactive_job_queue,
                supported_labels=supported_labels,
            )
        else:
            algorithm_config = PrespawnConfig(
                algorithm=ReconcileAlgorithm.PRESPAWN,
                base_quantity=base_quantity,
                vm_image=combination.image.name,
                vm_flavor=combination.flavor.name,
            )
        reconciler = Reconciler(
            platform_provider=platform_service,
            cloud_provider=cloud_service,
            metrics_provider=MetricsProvider(),
            # GITHUB_DEFAULT_LABELS = {"self-hosted", "linux"}
            config=ReconcilerConfig(labels=app_config.extra_labels, python_path=python_path),
            algorithm_config=algorithm_config,
        )

        while not loop_handler.kill_now:
            with lock:
                logger.info(RECONCILE_START_MSG)
                reconciler.reconcile()
            logger.info(RECONCILE_END_MSG)
            RECONCILE_ID_FILE.write_text(str(uuid.uuid4()), encoding="utf-8")

            sleep(app_config.reconcile_interval * 60)

        if algorithm_config.algorithm == ReconcileAlgorithm.REACTIVE:
            reactive_job_queue.close()
            queue_connection.close()


class SigtermLoopHandler:
    """Handles SIGTERM gracefully."""

    def __init__(self):
        self.kill_now = False

    def __enter__(self) -> "SigtermLoopHandler":
        """Register signal handler for SIGTERM."""
        signal.signal(signal.SIGTERM, self._exit_gracefully)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore signal handler."""
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    def _exit_gracefully(self, signum, frame):
        """Set kill signal to True."""
        self.kill_now = True
        print(
            f"Signal '{signal.strsignal(signal.SIGTERM)}' received. Will terminate.",
            file=sys.stderr,
        )
        sys.exit(signal.SIGTERM)
