# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Planner-driven pressure reconciler.

Creates or deletes runners based on pressure signals from the planner
service. Runs in two independent loops (create/delete) and coordinates
access to the underlying RunnerManager via the provided lock.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event, Lock
from typing import Optional

from github_runner_manager.errors import MissingServerConfigError
from github_runner_manager.manager.runner_manager import RunnerManager, RunnerMetadata
from github_runner_manager.planner_client import PlannerApiError, PlannerClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PressureReconcilerConfig:
    """Configuration for pressure reconciliation.

    Attributes:
        flavor_name: Name of the planner flavor to reconcile.
        reconcile_interval: Seconds between timer-based delete reconciliations.
        fallback_runners: Desired runner count to use while planner is unavailable.
        min_pressure: Minimum desired runner count (floor) for the flavor.
    """

    flavor_name: str
    reconcile_interval: int = 5 * 60
    fallback_runners: int = 0
    min_pressure: int = 0


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
        _planner: Client used to stream pressure updates.
        _config: Reconciler configuration.
        _lock: Shared lock to serialize operations with other reconcile loops.
        _stop: Event used to signal streaming loops to stop gracefully.
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

    def start_create_loop(self) -> None:  # pragma: no cover - long-running loop
        """Continuously create runners to satisfy planner pressure."""
        while not self._stop.is_set():
            try:
                for update in self._planner.stream_pressure(self._config.flavor_name):
                    if self._stop.is_set():
                        return
                    self._handle_create_runners(update.pressure)
            except PlannerApiError:
                logger.exception(
                    "Error in pressure stream loop, falling back to %s runners.",
                    self._config.fallback_runners,
                )
                self._handle_create_runners(self._config.fallback_runners)
                time.sleep(5)

    def start_delete_loop(self) -> None:  # pragma: no cover - long-running loop
        """Continuously delete runners using last seen pressure on a timer."""
        logger.debug("Delete loop: starting, interval=%ss", self._config.reconcile_interval)
        while not self._stop.wait(self._config.reconcile_interval):
            logger.debug("Delete loop: woke up, _last_pressure=%s", self._last_pressure)
            if self._last_pressure is None:
                logger.debug("Delete loop: no pressure seen yet, skipping.")
                continue
            self._handle_timer_reconcile(self._last_pressure)

    def stop(self) -> None:
        """Signal the reconciler loops to stop gracefully."""
        self._stop.set()

    def _handle_create_runners(self, pressure: int) -> None:
        """Create runners when desired exceeds current total.

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
            current_total = len(self._manager.get_runners())
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
                self._manager.create_runners(num=to_create, metadata=RunnerMetadata())
            except MissingServerConfigError:
                logger.exception(
                    "Unable to create runners due to missing server configuration (image/flavor)."
                )

    def _handle_timer_reconcile(self, pressure: int) -> None:
        """Clean up stale runners, then converge toward the desired count.

        Scales down (deletes) when current exceeds desired, and scales up
        (creates) when current falls below desired after cleanup.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        with self._lock:
            self._manager.cleanup()
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

    def _desired_total_from_pressure(self, pressure: int) -> int:
        """Compute desired runner total from planner pressure.

        Ensures non-negative totals and respects the configured `min_pressure`
        floor.

        Args:
            pressure: Current pressure value from planner.

        Returns:
            The desired total number of runners.
        """
        return max(pressure, self._config.min_pressure, 0)
