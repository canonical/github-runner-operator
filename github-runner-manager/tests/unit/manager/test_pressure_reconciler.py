"""Unit tests for PressureReconciler."""

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from threading import Lock
from types import SimpleNamespace

import pytest

from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    PressureReconcilerConfig,
)
from github_runner_manager.planner_client import PlannerApiError


class _FakeManager:
    """Lightweight runner manager stub for testing the reconciler."""

    def __init__(self, runners_count: int = 0):
        """Initialize with an optional number of pre-existing runners."""
        self._runners = [object() for _ in range(runners_count)]
        self.created_args: list[int] = []
        self.cleanup_called = 0

    def get_runners(self) -> list[object]:
        """Return the current list of runners."""
        return list(self._runners)

    def create_runners(self, num: int, metadata: object):  # noqa: ARG002
        """Record the creation request and extend the internal runner list."""
        self.created_args.append(num)
        if num > 0:
            self._runners.extend(object() for _ in range(num))

    def cleanup(self):
        """Increment the cleanup counter."""
        self.cleanup_called += 1


class _FakePlanner:
    """Planner client stub supplying pressure data for tests."""

    def __init__(
        self,
        stream_updates: list[int] | None = None,
        stream_raises: bool = False,
    ):
        """Initialize with configurable stream behavior."""
        self._stream_updates = stream_updates or []
        self._stream_raises = stream_raises

    def stream_pressure(self, name: str):  # noqa: ARG002
        """Yield pressure updates or raise PlannerApiError based on configuration.

        Yields:
            Namespace objects with a pressure attribute.
        """
        if self._stream_raises:
            raise PlannerApiError
        for p in self._stream_updates:
            yield SimpleNamespace(pressure=p)


def test_min_pressure_used_as_fallback_when_stream_errors(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler whose planner stream raises PlannerApiError and no prior pressure.
    act: Call start_create_loop.
    assert: min_pressure is used as fallback to create runners.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(stream_raises=True)
    cfg = PressureReconcilerConfig(flavor_name="small", min_pressure=2)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    def _stop_after_backoff(_seconds: int):
        """Stop the reconciler after the backoff sleep is triggered."""
        reconciler.stop()

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.sleep", _stop_after_backoff
    )
    reconciler.start_create_loop()

    assert 2 in mgr.created_args


def test_fallback_preserves_last_pressure_when_higher(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with last_pressure=10 and min_pressure=2 whose stream errors.
    act: Call start_create_loop.
    assert: The higher last_pressure is used as fallback instead of min_pressure.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(stream_raises=True)
    cfg = PressureReconcilerConfig(flavor_name="small", min_pressure=2)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    reconciler._last_pressure = 10

    def _stop_after_backoff(_seconds: int):
        """Stop the reconciler after the backoff sleep is triggered."""
        reconciler.stop()

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.sleep", _stop_after_backoff
    )
    reconciler.start_create_loop()

    assert 10 in mgr.created_args


def test_delete_loop_uses_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with a cached last_pressure value.
    act: Call start_delete_loop.
    assert: Cleanup runs and runners are created based on the cached pressure.
    """
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", reconcile_interval=60)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    reconciler._last_pressure = 3
    wait_calls = {"count": 0}

    def _wait(_interval: int) -> bool:
        """Return False once to enter the loop, then True to exit."""
        wait_calls["count"] += 1
        return wait_calls["count"] > 1

    monkeypatch.setattr(reconciler._stop, "wait", _wait)
    reconciler.start_delete_loop()

    assert mgr.cleanup_called == 1
    assert mgr.created_args == [3]


def test_delete_loop_skips_when_no_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with no cached pressure (None).
    act: Call start_delete_loop.
    assert: No cleanup or creation occurs.
    """
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", reconcile_interval=60)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    wait_calls = {"count": 0}

    def _wait(_interval: int) -> bool:
        """Return True (stop signal) after the second call."""
        wait_calls["count"] += 1
        return wait_calls["count"] > 1

    monkeypatch.setattr(reconciler._stop, "wait", _wait)
    reconciler.start_delete_loop()

    assert mgr.cleanup_called == 0


@pytest.mark.parametrize(
    "pressure, min_pressure, max_pressure, expected",
    [
        pytest.param(5, 0, 10, 5, id="within_bounds"),
        pytest.param(15, 0, 10, 10, id="clamped_to_max"),
        pytest.param(1, 3, 10, 3, id="raised_to_min"),
        pytest.param(15, 3, 10, 10, id="max_wins_over_pressure"),
        pytest.param(5, 0, 0, 5, id="zero_max_means_no_cap"),
        pytest.param(-1, 0, 0, 0, id="negative_clamped_to_zero"),
    ],
)
def test_desired_total_from_pressure_respects_bounds(
    pressure: int, min_pressure: int, max_pressure: int, expected: int
):
    """
    arrange: A reconciler with various min/max pressure configurations.
    act: Call _desired_total_from_pressure.
    assert: The result is clamped within the configured bounds.
    """
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(
        flavor_name="small", min_pressure=min_pressure, max_pressure=max_pressure
    )
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    assert reconciler._desired_total_from_pressure(pressure) == expected


def test_handle_timer_reconcile_uses_desired_total_not_raw_pressure():
    """
    arrange: A reconciler with 4 runners and min_pressure=5.
    act: Call _handle_timer_reconcile with pressure 0.
    assert: Cleanup runs and 1 runner is created to reach the min_pressure floor.
    """
    mgr = _FakeManager(runners_count=4)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", min_pressure=5)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_timer_reconcile(0)

    assert mgr.cleanup_called == 1
    assert mgr.created_args == [1]
