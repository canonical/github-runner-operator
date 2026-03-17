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
from github_runner_manager.manager.runner_manager import IssuedMetricEventsStats
from github_runner_manager.manager.vm_manager import HealthState
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.planner_client import PlannerApiError, PlannerConnectionError
from github_runner_manager.platform.platform_provider import PlatformRunnerState


class _FakeRunner:
    """Minimal runner stub with platform_state and health for metric counting."""

    def __init__(self, platform_state=None, health=None):
        """Initialize with optional platform state and health.

        Args:
            platform_state: The platform state of the runner.
            health: The health state of the runner.
        """
        self.platform_state = platform_state
        self.health = health


class _FakeManager:
    """Lightweight runner manager stub for testing the reconciler."""

    manager_name = "test-manager"

    def __init__(self, runners_count: int = 0, create_success_ratio: float = 1.0):
        """Initialize with an optional number of pre-existing runners.

        Args:
            runners_count: Number of pre-existing runners.
            create_success_ratio: Fraction of requested runners that succeed (0.0-1.0).
        """
        self._runners = [_FakeRunner() for _ in range(runners_count)]
        self.created_args: list[int] = []
        self.deleted_args: list[int] = []
        self.cleanup_called = 0
        self.get_runners_calls = 0
        self._create_success_ratio = create_success_ratio

    def get_runners(self) -> tuple:
        """Return the current list of runners."""
        self.get_runners_calls += 1
        return tuple(self._runners)

    def create_runners(self, num: int, metadata: object) -> tuple[str, ...]:  # noqa: ARG002
        """Record the creation request and extend the internal runner list."""
        self.created_args.append(num)
        actually_created = max(int(num * self._create_success_ratio), 0)
        if actually_created > 0:
            self._runners.extend(_FakeRunner() for _ in range(actually_created))
        return tuple(f"instance-{i}" for i in range(actually_created))

    def soft_delete_runners(self, num: int) -> int:
        """Record the deletion request and shrink the internal runner list."""
        self.deleted_args.append(num)
        to_remove = min(num, len(self._runners))
        if to_remove:
            self._runners = self._runners[:-to_remove]
        return to_remove

    def cleanup(self) -> IssuedMetricEventsStats:
        """Increment the cleanup counter and return empty metric stats."""
        self.cleanup_called += 1
        return {}


class _FakePlanner:
    """Planner client stub supplying pressure data for tests."""

    def __init__(
        self,
        stream_updates: list[int] | None = None,
        stream_exception: Exception | None = None,
    ):
        """Initialize with configurable stream behavior."""
        self._stream_updates = stream_updates or []
        self._stream_exception = stream_exception

    def stream_pressure(self, name: str):  # noqa: ARG002
        """Yield pressure updates or raise the configured exception.

        Yields:
            Namespace objects with a pressure attribute.
        """
        if self._stream_exception is not None:
            raise self._stream_exception
        for p in self._stream_updates:
            yield SimpleNamespace(pressure=p)


@pytest.mark.parametrize(
    "planner_error",
    [
        pytest.param(PlannerApiError("request failed"), id="planner_api_error"),
        pytest.param(PlannerConnectionError("connection dropped"), id="planner_connection_error"),
    ],
)
def test_min_pressure_used_as_fallback_when_stream_errors(
    monkeypatch: pytest.MonkeyPatch, planner_error: Exception
):
    """
    arrange: A reconciler whose planner stream raises a planner error and no prior pressure.
    act: Call start_create_loop.
    assert: min_pressure is used as fallback to create runners.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(stream_exception=planner_error)
    cfg = PressureReconcilerConfig(flavor_name="small", min_pressure=2)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    def _stop_after_backoff(_seconds: int) -> bool:
        """Stop the reconciler after the backoff wait is triggered."""
        reconciler.stop()
        return True

    monkeypatch.setattr(reconciler._stop, "wait", _stop_after_backoff)
    reconciler.start_create_loop()

    assert 2 in mgr.created_args


@pytest.mark.parametrize(
    "planner_error",
    [
        pytest.param(PlannerApiError("request failed"), id="planner_api_error"),
        pytest.param(PlannerConnectionError("connection dropped"), id="planner_connection_error"),
    ],
)
def test_fallback_preserves_last_pressure_when_higher(
    monkeypatch: pytest.MonkeyPatch, planner_error: Exception
):
    """
    arrange: A reconciler with last_pressure=10 and min_pressure=2 whose stream errors.
    act: Call start_create_loop.
    assert: The higher last_pressure is used as fallback instead of min_pressure.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(stream_exception=planner_error)
    cfg = PressureReconcilerConfig(flavor_name="small", min_pressure=2)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    reconciler._last_pressure = 10

    def _stop_after_backoff(_seconds: int) -> bool:
        """Stop the reconciler after the backoff wait is triggered."""
        reconciler.stop()
        return True

    monkeypatch.setattr(reconciler._stop, "wait", _stop_after_backoff)
    reconciler.start_create_loop()

    assert 10 in mgr.created_args


def test_timer_loop_uses_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with a cached last_pressure value.
    act: Call the reconcile loop (start_reconcile_loop).
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
    reconciler.start_reconcile_loop()

    assert mgr.cleanup_called == 1
    assert mgr.created_args == [3]


def test_timer_loop_skips_when_no_cached_pressure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with no cached pressure (None).
    act: Call the reconcile loop (start_reconcile_loop).
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
    reconciler.start_reconcile_loop()

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


def test_create_loop_uses_in_memory_count():
    """
    arrange: A reconciler with no runners.
    act: Call _handle_create_runners twice with same pressure.
    assert: get_runners() is NOT called — only the in-memory count is used.
    """
    mgr = _FakeManager()
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(3)
    reconciler._handle_create_runners(3)

    assert mgr.get_runners_calls == 0
    assert mgr.created_args == [3]


def test_in_memory_count_incremented_by_actual_successes():
    """
    arrange: A manager where only half of requested runners succeed.
    act: Call _handle_create_runners twice requesting 4 total.
    assert: _runner_count reflects only actual successes, causing a second create attempt.
    """
    mgr = _FakeManager(create_success_ratio=0.5)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(4)
    reconciler._handle_create_runners(4)

    # First call: desired=4, current=0, create 4, only 2 succeed -> _runner_count=2
    # Second call: desired=4, current=2, create 2, only 1 succeeds -> _runner_count=3
    assert mgr.created_args == [4, 2]
    assert reconciler._runner_count == 3


def test_zero_create_pauses_create_loop_until_reconcile():
    """
    arrange: A reconciler whose create call returns zero runners.
    act: Call _handle_create_runners twice with the same desired pressure.
    assert: The second call is skipped because creates are paused.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(4)
    reconciler._handle_create_runners(4)

    assert mgr.created_args == [4]
    assert reconciler._create_paused is True


def test_timer_reconcile_always_unpauses_create_loop():
    """
    arrange: A reconciler paused after zero-create, at desired count.
    act: Run timer reconcile when current matches desired (no create needed).
    assert: _create_paused is cleared even though no runners were created.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(2)
    assert reconciler._create_paused is True

    mgr._create_success_ratio = 1.0
    mgr._runners = [_FakeRunner(), _FakeRunner()]
    reconciler._handle_timer_reconcile(2)

    assert mgr.created_args == [2]
    assert reconciler._create_paused is False


def test_timer_reconcile_repauses_on_zero_create():
    """
    arrange: A reconciler paused after zero-create, reconcile needs to scale up.
    act: Run timer reconcile while creation still returns zero IDs.
    assert: _create_paused is set back to True after the failed scale-up.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(2)
    assert reconciler._create_paused is True

    reconciler._handle_timer_reconcile(2)

    assert mgr.created_args == [2, 2]
    assert reconciler._create_paused is True


def test_successful_create_does_not_pause():
    """
    arrange: A reconciler where creates succeed.
    act: Call _handle_create_runners with successful creation.
    assert: _create_paused remains False.
    """
    mgr = _FakeManager(create_success_ratio=1.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_create_runners(3)

    assert reconciler._create_paused is False


def test_reconcile_loop_syncs_in_memory_count(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with _runner_count out of sync with actual runners.
    act: Run the reconcile loop (start_reconcile_loop) once.
    assert: _runner_count is synced to the actual get_runners() count.
    """
    mgr = _FakeManager(runners_count=5)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small", reconcile_interval=60)
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    reconciler._last_pressure = 5
    reconciler._runner_count = 10  # Out of sync
    wait_calls = {"count": 0}

    def _wait(_interval: int) -> bool:
        """Return False once to enter the loop, then True to exit."""
        wait_calls["count"] += 1
        return wait_calls["count"] > 1

    monkeypatch.setattr(reconciler._stop, "wait", _wait)
    reconciler.start_reconcile_loop()

    assert reconciler._runner_count == 5


def test_timer_reconcile_scale_up_updates_in_memory_count():
    """
    arrange: A reconciler with 2 runners and a higher desired pressure.
    act: Call _handle_timer_reconcile so that it scales up from 2 to 5 runners.
    assert: _runner_count is updated to reflect the new total after scale-up.
    """
    mgr = _FakeManager(runners_count=2)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_timer_reconcile(5)

    assert mgr.created_args == [3]
    assert reconciler._runner_count == 5


def test_create_loop_syncs_runner_count_on_start(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with pre-existing runners and pressure matching the count.
    act: Call start_create_loop.
    assert: _runner_count is synced from get_runners() before processing pressure events,
        so no unnecessary runners are created.
    """
    mgr = _FakeManager(runners_count=3)
    planner = _FakePlanner(stream_updates=[3])
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    # stop after stream exhausts to avoid infinite loop
    original_stream = planner.stream_pressure

    def _stream_once(name):
        """Yield from original stream, then stop the reconciler."""
        yield from original_stream(name)
        reconciler.stop()

    monkeypatch.setattr(planner, "stream_pressure", _stream_once)
    reconciler.start_create_loop()

    assert reconciler._runner_count == 3
    assert mgr.created_args == []


def test_timer_reconcile_scales_down_with_soft_delete():
    """
    arrange: A reconciler with 5 runners and a lower desired pressure of 2.
    act: Call _handle_timer_reconcile.
    assert: soft_delete_runners is used to remove excess idle runners.
    """
    mgr = _FakeManager(runners_count=5)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    reconciler._handle_timer_reconcile(2)

    assert mgr.created_args == []
    assert mgr.deleted_args == [3]
    assert reconciler._runner_count == 2


def test_timer_reconcile_emits_reconciliation_metric(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with runners in various platform states.
    act: Call _handle_timer_reconcile with pressure 5.
    assert: A Reconciliation metric event is issued with correct idle/active counts.
    """
    mgr = _FakeManager()
    mgr._runners = [
        _FakeRunner(platform_state=PlatformRunnerState.IDLE),
        _FakeRunner(platform_state=PlatformRunnerState.BUSY),
        _FakeRunner(platform_state=PlatformRunnerState.OFFLINE, health=HealthState.HEALTHY),
    ]
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())

    issued_events: list = []
    monkeypatch.setattr(metric_events, "issue_event", lambda evt: issued_events.append(evt))

    reconciler._handle_timer_reconcile(5)

    assert len(issued_events) == 1
    event = issued_events[0]
    assert isinstance(event, metric_events.Reconciliation)
    assert event.flavor == "small"
    assert event.expected_runners == 5
    assert event.duration >= 0
    assert event.idle_runners == 2  # IDLE + OFFLINE+HEALTHY
    assert event.active_runners == 1
    assert event.crashed_runners == 0
