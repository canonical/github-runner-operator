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
from typing import Callable, Optional

from github_runner_manager.errors import MissingServerConfigError
from github_runner_manager.manager.runner_manager import RunnerManager, RunnerMetadata
from github_runner_manager.planner_client import PlannerApiError, PlannerClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PressureReconcilerConfig:
    """Configuration for pressure reconciliation.

    Attributes:
        flavor_name: Name of the planner flavor to reconcile.
        poll_interval: Seconds between pressure polls/backoff when needed.
    """

    flavor_name: str
    poll_interval: int = 30


class PressureReconciler:  # pylint: disable=too-few-public-methods
    """Continuously reconciles runner count against planner pressure.

    This reconciler keeps the total number of runners near the desired level
    indicated by the planner's pressure for a given flavor. It operates in two
    threads:
    - create loop: scales up when desired exceeds current total
    - delete loop: scales down when current exceeds desired

    Concurrency with any other reconcile loop is protected by a shared lock.

    Attributes:
        _manager: Runner manager used to list, create, and clean up runners.
        _planner: Client used to load flavor info and stream pressure updates.
        _flavor: Flavor name whose pressure should be reconciled.
        _poll_interval: Interval in seconds for polling/backoff activities.
        _lock: Shared lock to serialize operations with other reconcile loops.
        _stop: Event used to signal streaming loops to stop gracefully.
        _min_pressure: Minimum desired runner count derived from planner flavor.
    """

    def __init__(
        self,
        manager: RunnerManager,
        planner_client: PlannerClient,
        config: PressureReconcilerConfig,
    ) -> None:
        """Initialize reconciler state and dependencies.

        Args:
            manager: Runner manager interface for creating, cleaning up,
                and listing runners.
            planner_client: Client used to query planner flavor info and
                stream pressure updates.
            config: Reconciler configuration holding the target `flavor_name`
                and `poll_interval` for pressure checks.
        """
        self._manager = manager
        self._planner = planner_client
        self._flavor = config.flavor_name
        self._poll_interval = config.poll_interval

        self._lock = Lock()

        self._stop = Event()
        self._min_pressure: Optional[int] = None

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
        self._streaming_loop(self._handle_create)

    def start_delete_loop(self) -> None:  # pragma: no cover - long-running loop
        """Continuously delete runners when planner pressure decreases."""
        self._streaming_loop(self._handle_delete)

    def _streaming_loop(self, handler: Callable[[float], None]) -> None:
        """Consume planner pressure (stream) and apply handler until stopped."""
        while not self._stop.is_set():
            try:
                for update in self._planner.stream_pressure(self._flavor):
                    if self._stop.is_set():
                        return
                    handler(update.pressure)
            except PlannerApiError:
                if self._stop.is_set():
                    return
                logger.exception(
                    "Unhandled error in pressure stream loop. Retrying after backoff."
                )
                # Short backoff to avoid hot-looping on failures
                time.sleep(5)

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

    def _handle_delete(self, pressure: float) -> None:
        """Clean up then create missing runners if below desired.

        Args:
            pressure: Current pressure value used to compute desired total.
        """
        desired_total = self._desired_total_from_pressure(pressure)
        with self._lock:
            self._manager.cleanup_runners()
            current_total = len(self._manager.get_runners())
            if pressure <= current_total:
                logger.info(
                    "Pressure less than current runners (%s <= %s). No changes.",
                    pressure,
                    current_total,
                )
                return

            desired_pressure_difference = desired_total - current_total
            logger.info(
                "Pressure bigger than current runners (%s > %s). Creating runners.",
                pressure,
                current_total,
            )
            self._manager.create_runners(
                num=desired_pressure_difference, metadata=RunnerMetadata()
            )
