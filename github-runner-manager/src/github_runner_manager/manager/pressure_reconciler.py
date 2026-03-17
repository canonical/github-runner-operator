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
from github_runner_manager.configuration.base import NonReactiveCombination, UserInfo
from github_runner_manager.errors import IssueMetricEventError, MissingServerConfigError
from github_runner_manager.manager.runner_manager import (
    IssuedMetricEventsStats,
    RunnerInstance,
    RunnerManager,
    RunnerMetadata,
)
from github_runner_manager.manager.vm_manager import HealthState
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics.reconcile import (
    BUSY_RUNNERS_COUNT,
    EXPECTED_RUNNERS_COUNT,
    IDLE_RUNNERS_COUNT,
    RECONCILE_DURATION_SECONDS,
)
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
from github_runner_manager.platform.platform_provider import PlatformRunnerState

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


class PressureReconciler:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
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
    back down. API-level creation failures (where no IDs are returned) pause
    the create loop entirely until the next reconcile loop run, which
    re-enables creation and creates if still needed.

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
        _create_paused: True when creation returned zero IDs, cleared by reconcile loop.
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
        self._create_paused: bool = False

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
                if self._stop.is_set():
                    return
                self._handle_create_runners(fallback)
                self._stop.wait(5)
            except PlannerApiError:
                fallback = max(self._last_pressure or 0, self._config.min_pressure)
                logger.exception(
                    "Error in pressure stream loop for flavor %s, falling back to %s runners.",
                    self._config.flavor_name,
                    fallback,
                )
                if self._stop.is_set():
                    return
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
            if self._create_paused:
                logger.warning(
                    "Create loop: paused after zero-create, waiting for reconcile"
                    " (desired=%s current=%s)",
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
            if actually_created == 0:
                self._create_paused = True
                logger.warning("Create loop: pausing until next reconcile after zero-create")

    def _handle_timer_reconcile(self, pressure: int) -> None:
        """Clean up stale runners, sync in-memory count, then scale up or down.

        Runs cleanup to remove unhealthy/stale runners, syncs _runner_count
        from get_runners(), creates runners if current falls below desired,
        and soft-deletes idle runners if current exceeds desired.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        start_timestamp = time.time()
        metric_stats: IssuedMetricEventsStats = {}
        runner_list: tuple[RunnerInstance, ...] = ()
        try:
            with self._lock:
                metric_stats = self._manager.cleanup()
                runner_list = self._manager.get_runners()
                current_total = len(runner_list)
                self._runner_count = current_total
                if self._create_paused:
                    logger.info("Reconcile loop: unpausing create loop after state sync")
                self._create_paused = False
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
                    if actually_created == 0:
                        self._create_paused = True
                        logger.warning("Reconcile loop: re-pausing create loop after zero-create")
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
        finally:
            self._issue_reconciliation_metric(
                runner_list=runner_list,
                metric_stats=metric_stats,
                desired_total=desired_total,
                start_timestamp=start_timestamp,
            )

    def _issue_reconciliation_metric(
        self,
        runner_list: tuple[RunnerInstance, ...],
        metric_stats: IssuedMetricEventsStats,
        desired_total: int,
        start_timestamp: float,
    ) -> None:
        """Issue Reconciliation metric event and update Prometheus gauges.

        Args:
            runner_list: Current runners from get_runners(), reused to avoid a
                redundant OpenStack API call.
            metric_stats: Event type counts from cleanup.
            desired_total: Expected number of runners.
            start_timestamp: When the reconciliation started.
        """
        end_timestamp = time.time()
        duration = end_timestamp - start_timestamp
        manager_name = self._manager.manager_name
        RECONCILE_DURATION_SECONDS.labels(manager_name).observe(duration)

        idle = sum(1 for r in runner_list if r.platform_state == PlatformRunnerState.IDLE)
        offline_healthy = sum(
            1
            for r in runner_list
            if r.platform_state == PlatformRunnerState.OFFLINE and r.health == HealthState.HEALTHY
        )
        available = idle + offline_healthy
        active = sum(1 for r in runner_list if r.platform_state == PlatformRunnerState.BUSY)
        BUSY_RUNNERS_COUNT.labels(manager_name).set(active)
        IDLE_RUNNERS_COUNT.labels(manager_name).set(idle)
        EXPECTED_RUNNERS_COUNT.labels(manager_name).set(desired_total)

        try:
            metric_events.issue_event(
                metric_events.Reconciliation(
                    timestamp=end_timestamp,
                    flavor=self._config.flavor_name,
                    # Only reflects cleanup() stats; scale-down via soft_delete_runners
                    # returns an int, so its metric events are not captured here.
                    crashed_runners=metric_stats.get(metric_events.RunnerStart, 0)
                    - metric_stats.get(metric_events.RunnerStop, 0),
                    idle_runners=available,
                    active_runners=active,
                    expected_runners=desired_total,
                    duration=duration,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue Reconciliation metric")

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
