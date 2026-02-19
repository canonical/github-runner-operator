"""Unit tests for PressureReconciler."""

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    PressureReconcilerConfig,
)
from github_runner_manager.planner_client import PlannerApiError


class _FakeManager:
    """Lightweight runner manager stub for testing the reconciler."""

    def __init__(self, runners_count: int = 0):
        self._runners = [object() for _ in range(runners_count)]
        self.created_args: list[int] = []
        self.cleanup_called = 0

    def get_runners(self) -> list[object]:
        return list(self._runners)

    def create_runners(self, num: int, metadata: object):  # noqa: ARG002
        self.created_args.append(num)
        if num > 0:
            self._runners.extend(object() for _ in range(num))

    def cleanup_runners(self):
        self.cleanup_called += 1


class _FakePlanner:
    """Planner client stub supplying flavor and pressure data for tests."""

    def __init__(
        self,
        flavor_min_pressure: int | None = None,
        stream_updates: list[float] | None = None,
        stream_raises: bool = False,
    ):
        self._flavor_min_pressure = flavor_min_pressure
        self._stream_updates = stream_updates or []
        self._stream_raises = stream_raises

    def get_flavor(self, name: str):  # noqa: ARG002
        return SimpleNamespace(name="small", minimum_pressure=self._flavor_min_pressure)

    def stream_pressure(self, name: str):  # noqa: ARG002
        if self._stream_raises:
            raise PlannerApiError
        for p in self._stream_updates:
            yield SimpleNamespace(pressure=p)


def test_fallback_runners_used_when_stream_errors(monkeypatch: pytest.MonkeyPatch):
    """Planner stream failures should trigger fallback runner creation."""
    mgr = _FakeManager()
    planner = _FakePlanner(stream_raises=True)
    cfg = PressureReconcilerConfig(flavor_name="small", fallback_runners=2)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    def _stop_after_backoff(_seconds: int):
        reconciler.stop()

    monkeypatch.setattr("github_runner_manager.manager.pressure_reconciler.time.sleep", _stop_after_backoff)
    reconciler.start_create_loop()

    assert 2 in mgr.created_args


def test_delete_loop_uses_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """Delete loop should call handler with cached pressure, not planner stream."""
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", reconcile_interval=1)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    reconciler._last_pressure = 3.0  # noqa: SLF001
    handler = MagicMock()
    monkeypatch.setattr(reconciler, "_handle_timer_reconcile", handler)
    monkeypatch.setattr(
        reconciler._stop,
        "wait",
        lambda _interval: True if handler.call_count else False,
    )  # noqa: SLF001

    reconciler.start_delete_loop()

    handler.assert_called_once_with(3.0)


def test_delete_loop_skips_when_no_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """Delete loop should not run delete handler until pressure is observed."""
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", reconcile_interval=1)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    handler = MagicMock()
    monkeypatch.setattr(reconciler, "_handle_timer_reconcile", handler)
    wait_calls = {"count": 0}

    def _wait(_interval: int) -> bool:
        wait_calls["count"] += 1
        return wait_calls["count"] > 1

    monkeypatch.setattr(reconciler._stop, "wait", _wait)  # noqa: SLF001
    reconciler.start_delete_loop()

    assert handler.call_count == 0


def test_handle_timer_reconcile_uses_desired_total_not_raw_pressure():
    """Delete path should compare against desired total (with minimum pressure floor)."""
    mgr = _FakeManager(runners_count=4)
    planner = _FakePlanner(flavor_min_pressure=5)
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_timer_reconcile(0.0)

    assert mgr.cleanup_called == 1
    assert mgr.created_args == [1]
