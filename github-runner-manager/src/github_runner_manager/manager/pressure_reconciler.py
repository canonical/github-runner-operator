# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Planner-driven pressure reconciler.

Creates or deletes runners based on pressure signals from the planner
service. Runs in two independent loops (create/delete) and coordinates
access to the underlying RunnerManager via the provided lock.
"""

from __future__ import annotations

import getpass
import grp
import logging
import os
import time
from dataclasses import dataclass
from threading import Event, Lock
from typing import Optional

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import UserInfo
from github_runner_manager.errors import MissingServerConfigError
from github_runner_manager.manager.runner_manager import RunnerManager, RunnerMetadata
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
)
from github_runner_manager.planner_client import PlannerApiError, PlannerClient, PlannerConfiguration
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PressureReconcilerConfig:
    """Configuration for pressure reconciliation.

    Attributes:
        flavor_name: Name of the planner flavor to reconcile.
        reconcile_interval: Minutes between timer-based delete reconciliations.
        fallback_runners: Desired runner count to use while planner is unavailable.
    """

    flavor_name: str
    reconcile_interval: int = 5
    fallback_runners: int = 0


class PressureReconciler:  # pylint: disable=too-few-public-methods
    """Continuously reconciles runner count against planner pressure.

    This reconciler keeps the total number of runners near the desired level
    indicated by the planner's pressure for a given flavor. It operates in two
    threads:
    - create loop: scales up when desired exceeds current total
    - delete loop: scales down when current exceeds desired

    Concurrency with any other reconcile loop is protected by a shared lock.

    The delete loop uses the last pressure seen by the create loop rather than
    fetching a fresh value, so it may act on a stale reading if pressure changed
    between stream events. This is an accepted trade-off: the window is bounded
    by the stream update frequency, and any over-deletion is self-correcting
    because the create loop will scale back up on the next pressure event.

    Attributes:
        _manager: Runner manager used to list, create, and clean up runners.
        _planner: Client used to load flavor info and stream pressure updates.
        _flavor: Flavor name whose pressure should be reconciled.
        _config: Reconciler configuration.
        _lock: Shared lock to serialize operations with other reconcile loops.
        _stop: Event used to signal streaming loops to stop gracefully.
        _min_pressure: Minimum desired runner count derived from planner flavor.
        _last_pressure: Last pressure value seen in the create stream.
    """

    def __init__(
        self,
        manager: RunnerManager,
        planner_client: PlannerClient,
        config: PressureReconcilerConfig,
        lock: Lock,
    ) -> None:
        """Initialize reconciler state and dependencies.

        Args:
            manager: Runner manager interface for creating, cleaning up,
                and listing runners.
            planner_client: Client used to query planner flavor info and
                stream pressure updates.
            config: Reconciler configuration.
            lock: Shared lock to serialize operations with other reconcile loops.
        """
        self._manager = manager
        self._planner = planner_client
        self._flavor = config.flavor_name
        self._config = config
        self._lock = lock

        self._stop = Event()
        self._min_pressure: Optional[int] = None
        self._last_pressure: Optional[float] = None

        try:
            flavor = self._planner.get_flavor(self._flavor)
            self._min_pressure = flavor.minimum_pressure
            logger.info(
                "Planner flavor loaded: name=%s, minimum_pressure=%s",
                flavor.name,
                flavor.minimum_pressure,
            )
        except PlannerApiError:
            logger.warning(
                "Planner flavor info unavailable for '%s'. Proceeding without minimum_pressure.",
                self._flavor,
            )

    def start_create_loop(self) -> None:  # pragma: no cover - long-running loop
        """Continuously create runners to satisfy planner pressure."""
        while not self._stop.is_set():
            try:
                for update in self._planner.stream_pressure(self._flavor):
                    if self._stop.is_set():
                        return
                    self._handle_create(update.pressure)
            except PlannerApiError:
                if self._stop.is_set():
                    return
                logger.exception(
                    "Unhandled error in pressure stream loop. Retrying after backoff."
                )
                self._handle_create(float(self._config.fallback_runners))
                # Short backoff to avoid hot-looping on failures.
                time.sleep(5)

    def start_delete_loop(self) -> None:  # pragma: no cover - long-running loop
        """Continuously delete runners using last seen pressure on a timer."""
        interval_seconds = self._config.reconcile_interval * 60
        logger.debug("Delete loop: starting, interval=%ss", interval_seconds)
        while not self._stop.is_set():
            if self._stop.wait(interval_seconds):
                return
            logger.debug("Delete loop: woke up, _last_pressure=%s", self._last_pressure)
            if self._last_pressure is None:
                logger.debug("Delete loop: no pressure seen yet, skipping.")
                continue
            self._handle_timer_reconcile(self._last_pressure)

    def stop(self) -> None:
        """Signal the reconciler loops to stop gracefully."""
        self._stop.set()

    def _desired_total_from_pressure(self, pressure: float) -> int:
        """Compute desired runner total from planner pressure.

        Ensures non-negative totals and respects planner `minimum_pressure`
        if available.

        Args:
            pressure: Current pressure value from planner.

        Returns:
            The desired total number of runners.
        """
        # Ensure we never drop below a configured minimum pressure (if available).
        base = int(pressure)
        if self._min_pressure is not None:
            base = max(base, int(self._min_pressure))
        return max(base, 0)

    def _handle_create(self, pressure: float) -> None:
        """Create runners when desired exceeds current total.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        logger.debug("Create loop: pressure=%.2f, desired=%s, updating _last_pressure", pressure, desired_total)
        self._last_pressure = pressure
        with self._lock:
            current_total = len(self._manager.get_runners())
            to_create = max(desired_total - current_total, 0)
            if to_create <= 0:
                logger.debug(
                    "Create loop: nothing to do (desired=%s current=%s)",
                    desired_total,
                    current_total,
                )
                return
            logger.info(
                "Create loop: creating %s runners (desired=%s current=%s)",
                to_create,
                desired_total,
                current_total,
            )
            try:
                self._manager.create_runners(num=to_create, metadata=RunnerMetadata())
            except MissingServerConfigError:
                logger.exception(
                    "Unable to create runners due to missing server configuration (image/flavor)."
                )

    def _handle_timer_reconcile(self, pressure: float) -> None:
        """Clean up stale runners, then converge toward the desired count.

        Scales down (deletes) when current exceeds desired, and scales up
        (creates) when current falls below desired after cleanup.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        with self._lock:
            self._manager.cleanup_runners()
            current_total = len(self._manager.get_runners())
            if current_total > desired_total:
                to_delete = current_total - desired_total
                logger.info(
                    "Timer: scaling down %s runners (desired=%s current=%s)",
                    to_delete,
                    desired_total,
                    current_total,
                )
                self._manager.delete_runners(num=to_delete)
            elif current_total < desired_total:
                to_create = desired_total - current_total
                logger.info(
                    "Timer: scaling up %s runners (desired=%s current=%s)",
                    to_create,
                    desired_total,
                    current_total,
                )
                self._manager.create_runners(num=to_create, metadata=RunnerMetadata())
            else:
                logger.info(
                    "Timer: no changes needed (desired=%s current=%s)",
                    desired_total,
                    current_total,
                )


def build_pressure_reconciler(config: ApplicationConfiguration, lock: Lock) -> PressureReconciler:
    """Construct a PressureReconciler from application configuration.

    Args:
        config: Application configuration.
        lock: Shared lock to serialize operations with other reconcile loops.

    Returns:
        A fully constructed PressureReconciler.
    """
    combinations = config.non_reactive_configuration.combinations
    first_combo = combinations[0] if combinations else None
    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)
    manager = RunnerManager(
        manager_name=config.name,
        platform_provider=GitHubRunnerPlatform.build(
            prefix=config.openstack_configuration.vm_prefix,
            github_configuration=config.github_config,
        ),
        cloud_runner_manager=OpenStackRunnerManager(
            config=OpenStackRunnerManagerConfig(
                allow_external_contributor=config.allow_external_contributor,
                prefix=config.openstack_configuration.vm_prefix,
                credentials=config.openstack_configuration.credentials,
                server_config=(
                    None
                    if not first_combo
                    else OpenStackServerConfig(
                        image=first_combo.image.name,
                        flavor=first_combo.flavor.name,
                        network=config.openstack_configuration.network,
                    )
                ),
                service_config=config.service_config,
            ),
            user=user,
        ),
        labels=(
            list(config.extra_labels)
            + ([] if not first_combo else (first_combo.image.labels + first_combo.flavor.labels))
        ),
    )
    return PressureReconciler(
        manager=manager,
        planner_client=PlannerClient(
            PlannerConfiguration(base_url=config.planner_url, token=config.planner_token)
        ),
        config=PressureReconcilerConfig(
            flavor_name=first_combo.flavor.name if first_combo else "",
            reconcile_interval=config.reconcile_interval,
            fallback_runners=first_combo.base_virtual_machines if first_combo else 0,
        ),
        lock=lock,
    )
