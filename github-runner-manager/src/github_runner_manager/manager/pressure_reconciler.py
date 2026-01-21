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
    """Configuration for pressure reconciliation."""

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
    """

    def __init__(
        self,
        manager: RunnerManager,
        planner_client: PlannerClient,
        config: PressureReconcilerConfig,
    ) -> None:
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
        # Ensure we never drop below a configured minimum pressure (if available).
        base = int(pressure)
        if self._min_pressure is not None:
            base = max(base, int(self._min_pressure))
        return max(base, 0)

    def _handle_create(self, pressure: float) -> None:
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
            except Exception:
                logger.exception("Unexpected error while creating runners.")

    def _handle_delete(self, pressure: float) -> None:
        desired_total = self._desired_total_from_pressure(pressure)
        with self._lock:
            self._manager.cleanup_runners()
            pressure = self._planner.get_pressure(self._flavor).pressure
            current_total = len(self._manager.get_runners())
            if pressure <= current_total:
                logger.info(
                    "Pressure less than current runners (%s <= %s). No changes.",
                    pressure,
                    current_total,
                )
                return

            desired_pressure_difference = int(pressure) - desired_total
            logger.info(
                "Pressure bigger than current runners (%s > %s). Creating runners.",
                pressure,
                current_total,
            )
            self._manager.create_runners(
                num=desired_pressure_difference, metadata=RunnerMetadata()
            )
