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

    def __init__(self, runners_count: int = 0, create_success_ratio: float = 1.0):
        """Initialize with an optional number of pre-existing runners.

        Args:
            runners_count: Number of pre-existing runners.
            create_success_ratio: Fraction of requested runners that succeed (0.0-1.0).
        """
        self._runners = [object() for _ in range(runners_count)]
        self.created_args: list[int] = []
        self.deleted_args: list[int] = []
        self.cleanup_called = 0
        self.get_runners_calls = 0
        self._create_success_ratio = create_success_ratio

    def get_runners(self) -> list[object]:
        """Return the current list of runners."""
        self.get_runners_calls += 1
        return list(self._runners)

    def create_runners(self, num: int, metadata: object) -> tuple[str, ...]:  # noqa: ARG002
        """Record the creation request and extend the internal runner list."""
        self.created_args.append(num)
        actually_created = max(int(num * self._create_success_ratio), 0)
        if actually_created > 0:
            self._runners.extend(object() for _ in range(actually_created))
        return tuple(f"instance-{i}" for i in range(actually_created))

    def soft_delete_runners(self, num: int) -> int:
        """Record the deletion request and shrink the internal runner list."""
        self.deleted_args.append(num)
        to_remove = min(num, len(self._runners))
        if to_remove:
            self._runners = self._runners[:-to_remove]
        return to_remove

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


def test_create_loop_applies_backoff_after_zero_create(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler whose first create call returns zero runners.
    act: Call _handle_create_runners twice with the same desired pressure.
    assert: The second call is skipped while the create-loop backoff is active.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter([0.0, 1.0, 1.0])

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    reconciler._handle_create_runners(4)
    reconciler._handle_create_runners(4)

    assert mgr.created_args == [4]
    assert reconciler._create_backoff.delay == 5
    assert reconciler._create_backoff.until == 6.0


def test_create_loop_exponential_backoff_grows_on_repeated_zero_create(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: A reconciler with repeated zero-create attempts after each backoff expires.
    act: Call _handle_create_runners twice after allowing each backoff window to pass.
    assert: The backoff grows exponentially.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter([0.0, 0.0, 5.0, 5.0])

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    reconciler._handle_create_runners(2)
    reconciler._handle_create_runners(2)

    assert mgr.created_args == [2, 2]
    assert reconciler._create_backoff.delay == 10
    assert reconciler._create_backoff.until == 15.0


def test_successful_create_resets_backoff(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with a prior zero-create backoff and then a successful create.
    act: Let the backoff expire and call _handle_create_runners again.
    assert: The create-loop backoff state is cleared after success.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter([0.0, 0.0, 5.0])

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    reconciler._handle_create_runners(2)
    mgr._create_success_ratio = 1.0
    reconciler._handle_create_runners(2)

    assert mgr.created_args == [2, 2]
    assert reconciler._create_backoff.delay == 0
    assert reconciler._create_backoff.until == 0.0


def test_create_backoff_is_capped_at_max(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with repeated zero-create attempts after each backoff expires.
    act: Repeatedly call _handle_create_runners after each backoff window passes.
    assert: The backoff delay does not grow beyond the configured maximum.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter(
        [0.0, 0.0, 5.0, 5.0, 15.0, 15.0, 35.0, 35.0, 75.0, 75.0, 155.0, 155.0, 315.0, 315.0]
    )

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    for _ in range(7):
        reconciler._handle_create_runners(1)

    assert reconciler._create_backoff.delay == 300
    assert reconciler._create_backoff.until == 615.0


def test_timer_reconcile_success_resets_create_loop_backoff(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A reconciler with active create-loop backoff after a zero-create attempt.
    act: Run timer reconcile after creation starts succeeding.
    assert: The create-loop backoff is cleared.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter([0.0, 0.0])

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    reconciler._handle_create_runners(2)
    mgr._create_success_ratio = 1.0
    reconciler._handle_timer_reconcile(2)

    assert mgr.created_args == [2, 2]
    assert reconciler._create_backoff.delay == 0
    assert reconciler._create_backoff.until == 0.0


def test_timer_reconcile_zero_create_does_not_update_create_loop_backoff(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: A reconciler with active create-loop backoff after a zero-create attempt.
    act: Run timer reconcile while runner creation still returns zero IDs.
    assert: The timer reconcile does not change the create-loop backoff state.
    """
    mgr = _FakeManager(create_success_ratio=0.0)
    planner = _FakePlanner()
    cfg = PressureReconcilerConfig(flavor_name="small")
    reconciler = PressureReconciler(mgr, planner, cfg, lock=Lock())
    monotonic_values = iter([0.0, 0.0])

    monkeypatch.setattr(
        "github_runner_manager.manager.pressure_reconciler.time.monotonic",
        lambda: next(monotonic_values),
    )

    reconciler._handle_create_runners(2)
    backoff_before = reconciler._create_backoff
    reconciler._handle_timer_reconcile(2)

    assert mgr.created_args == [2, 2]
    assert reconciler._create_backoff == backoff_before


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
