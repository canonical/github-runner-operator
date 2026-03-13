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
from dataclasses import dataclass
from threading import Event, Lock
from typing import Optional

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.configuration.base import NonReactiveCombination, UserInfo
from github_runner_manager.errors import MissingServerConfigError
from github_runner_manager.manager.runner_manager import RunnerManager, RunnerMetadata
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
)
from github_runner_manager.planner_client import (
    PlannerApiError,
    PlannerClient,
    PlannerConfiguration,
    PlannerConnectionError,
)
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PressureReconcilerConfig:
    """Configuration for pressure reconciliation.

    Attributes:
        flavor_name: Name of the planner flavor to reconcile.
        reconcile_interval: Minutes between timer-based delete reconciliations.
        min_pressure: Minimum desired runner count (floor) for the flavor.
            Also used as fallback when the planner is unavailable.
        max_pressure: Maximum desired runner count (ceiling). 0 means no cap.
    """

    flavor_name: str
    reconcile_interval: int = 5
    min_pressure: int = 0
    max_pressure: int = 0


class PressureReconciler:  # pylint: disable=too-few-public-methods
    """Continuously reconciles runner count against planner pressure.

    This reconciler keeps the total number of runners near the desired level
    indicated by the planner's pressure for a given flavor. It operates in two
    threads:
    - create loop: scales up when desired exceeds current total
    - reconcile loop: cleans up stale runners, syncs state, scales up/down as needed

    Concurrency with any other reconcile loop is protected by a shared lock.

    The create loop tracks runners via an in-memory count rather than calling
    get_runners() on every pressure event, avoiding expensive OpenStack and
    GitHub API calls. Runner creation is fire-and-forget: the count is
    incremented by the number of IDs returned, even though VMs may fail to
    boot afterwards. This provides a natural backoff for post-creation
    failures (e.g. VMs that fail to boot): the in-memory count stays high
    and prevents further creation attempts until the reconcile loop runs,
    queries the real OpenStack state via get_runners(), and syncs the count
    back down. Note that API-level creation failures (where no IDs are
    returned) do not benefit from this backoff — the create loop will retry
    on the next pressure event, which is the desired behavior when the API
    recovers quickly.

    The reconcile loop uses the last pressure seen by the create loop rather than
    fetching a fresh value, so it may act on a stale reading if pressure changed
    between stream events. This is an accepted trade-off: the window is bounded
    by the stream update frequency.

    Attributes:
        _manager: Runner manager used to list, create, and clean up runners.
        _planner: Client used to stream pressure updates.
        _config: Reconciler configuration.
        _lock: Shared lock to serialize operations with other reconcile loops.
        _stop: Event used to signal streaming loops to stop gracefully.
        _last_pressure: Last pressure value seen in the create stream.
        _runner_count: In-memory runner count used by the create loop.
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
            planner_client: Client used to stream pressure updates.
            config: Reconciler configuration.
            lock: Shared lock to serialize operations with other reconcile loops.
        """
        self._manager = manager
        self._planner = planner_client
        self._config = config
        self._lock = lock

        self._stop = Event()
        self._last_pressure: Optional[int] = None
        self._runner_count: int = 0

    def start_create_loop(self) -> None:
        """Continuously create runners to satisfy planner pressure."""
        with self._lock:
            self._runner_count = len(self._manager.get_runners())
        logger.info("Create loop: initial sync, _runner_count=%s", self._runner_count)
        while not self._stop.is_set():
            try:
                for update in self._planner.stream_pressure(self._config.flavor_name):
                    if self._stop.is_set():
                        return
                    self._handle_create_runners(update.pressure)
            except PlannerConnectionError as exc:
                fallback = max(self._last_pressure or 0, self._config.min_pressure)
                logger.warning(
                    "Pressure stream interrupted for flavor %s (%s), falling back to %s runners.",
                    self._config.flavor_name,
                    exc,
                    fallback,
                )
                self._handle_create_runners(fallback)
                self._stop.wait(5)
            except PlannerApiError:
                fallback = max(self._last_pressure or 0, self._config.min_pressure)
                logger.exception(
                    "Error in pressure stream loop for flavor %s, falling back to %s runners.",
                    self._config.flavor_name,
                    fallback,
                )
                self._handle_create_runners(fallback)
                self._stop.wait(5)

    def start_reconcile_loop(self) -> None:
        """Periodically reconcile runners: sync state, scale up/down, and clean up."""
        interval_seconds = self._config.reconcile_interval * 60
        logger.debug("Reconcile loop: starting, interval=%ss", interval_seconds)
        while not self._stop.wait(interval_seconds):
            logger.debug("Reconcile loop: woke up, _last_pressure=%s", self._last_pressure)
            if self._last_pressure is None:
                logger.debug("Reconcile loop: no pressure seen yet, skipping.")
                continue
            self._handle_timer_reconcile(self._last_pressure)

    def stop(self) -> None:
        """Signal the reconciler loops to stop gracefully."""
        self._stop.set()

    def _handle_create_runners(self, pressure: int) -> None:
        """Create runners when desired exceeds current total.

        Uses an in-memory runner count instead of calling get_runners() to
        avoid expensive OpenStack and GitHub API calls on every pressure event.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        logger.debug(
            "Create loop: pressure=%s, desired=%s, updating _last_pressure",
            pressure,
            desired_total,
        )
        self._last_pressure = pressure
        with self._lock:
            current_total = self._runner_count
            to_create = max(desired_total - current_total, 0)
            if to_create <= 0:
                logger.info(
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
                created_ids = self._manager.create_runners(
                    num=to_create, metadata=RunnerMetadata()
                )
            except MissingServerConfigError:
                logger.exception(
                    "Unable to create runners due to missing server configuration"
                    " (image/flavor)."
                )
                return
            actually_created = len(created_ids)
            if actually_created < to_create:
                logger.error(
                    "Create loop: only %s/%s runners created",
                    actually_created,
                    to_create,
                )
            self._runner_count = current_total + actually_created

    def _handle_timer_reconcile(self, pressure: int) -> None:
        """Clean up stale runners, sync in-memory count, then scale up or down.

        Runs cleanup to remove unhealthy/stale runners, syncs _runner_count
        from get_runners(), creates runners if current falls below desired,
        and soft-deletes idle runners if current exceeds desired.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        with self._lock:
            self._manager.cleanup()
            current_total = len(self._manager.get_runners())
            self._runner_count = current_total
            if current_total < desired_total:
                to_create = desired_total - current_total
                logger.info(
                    "Reconcile loop: scaling up %s runners (desired=%s current=%s)",
                    to_create,
                    desired_total,
                    current_total,
                )
                try:
                    created_ids = self._manager.create_runners(
                        num=to_create, metadata=RunnerMetadata()
                    )
                except MissingServerConfigError:
                    logger.exception(
                        "Unable to create runners due to missing server configuration"
                        " (image/flavor)."
                    )
                    return
                actually_created = len(created_ids)
                if actually_created < to_create:
                    logger.error(
                        "Reconcile loop: only %s/%s runners created",
                        actually_created,
                        to_create,
                    )
                self._runner_count += actually_created
            elif current_total > desired_total:
                to_delete = current_total - desired_total
                logger.info(
                    "Reconcile loop: scaling down %s runners (desired=%s current=%s)",
                    to_delete,
                    desired_total,
                    current_total,
                )
                actually_deleted = self._manager.soft_delete_runners(num=to_delete)
                self._runner_count = max(current_total - actually_deleted, 0)
            else:
                logger.info(
                    "Reconcile loop: at desired count (desired=%s current=%s)",
                    desired_total,
                    current_total,
                )

    def _desired_total_from_pressure(self, pressure: int) -> int:
        """Compute desired runner total from planner pressure.

        Ensures non-negative totals and respects the configured `min_pressure`
        floor.

        Args:
            pressure: Current pressure value from planner.

        Returns:
            The desired total number of runners.
        """
        total = max(pressure, self._config.min_pressure, 0)
        if self._config.max_pressure > 0 and total > self._config.max_pressure:
            logger.info(
                "Pressure %s exceeds max_pressure %s, clamping to %s",
                pressure,
                self._config.max_pressure,
                self._config.max_pressure,
            )
            total = self._config.max_pressure
        return total


def build_pressure_reconciler(config: ApplicationConfiguration, lock: Lock) -> PressureReconciler:
    """Construct a PressureReconciler from application configuration.

    Args:
        config: Application configuration.
        lock: Shared lock to serialize operations with other reconcile loops.

    Raises:
        ValueError: If no non-reactive combinations are configured.

    Returns:
        A fully constructed PressureReconciler.
    """
    combinations = config.non_reactive_configuration.combinations
    if not combinations:
        raise ValueError(
            "Cannot build PressureReconciler: no non-reactive combinations configured."
        )
    first = combinations[0]
    manager = _build_runner_manager(config, first)
    return PressureReconciler(
        manager=manager,
        planner_client=PlannerClient(
            PlannerConfiguration(base_url=config.planner_url, token=config.planner_token)
        ),
        config=PressureReconcilerConfig(
            flavor_name=config.name,
            reconcile_interval=config.reconcile_interval,
            min_pressure=first.base_virtual_machines,
            max_pressure=first.max_total_virtual_machines,
        ),
        lock=lock,
    )


def _build_runner_manager(
    config: ApplicationConfiguration, combination: NonReactiveCombination
) -> RunnerManager:
    """Build a RunnerManager from application config and a flavor/image combination.

    Args:
        config: Application configuration.
        combination: The flavor/image combination to use for OpenStack VMs.

    Returns:
        A configured RunnerManager instance.
    """
    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)
    return RunnerManager(
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
                server_config=OpenStackServerConfig(
                    image=combination.image.name,
                    flavor=combination.flavor.name,
                    network=config.openstack_configuration.network,
                ),
                service_config=config.service_config,
            ),
            user=user,
        ),
        labels=list(config.extra_labels) + combination.image.labels + combination.flavor.labels,
    )
