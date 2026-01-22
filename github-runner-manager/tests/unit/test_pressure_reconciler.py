"""Unit tests for PressureReconciler."""

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from types import SimpleNamespace

import pytest

from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    PressureReconcilerConfig,
)


class _FakeManager:
    """Lightweight runner manager stub for testing the reconciler."""

    def __init__(self, runners_count: int = 0):
        """Initialize the fake manager with a starting runner count.

        Args:
            runners_count: Number of pre-existing runners to simulate.
        """
        self._runners = [object() for _ in range(runners_count)]
        self.created_args: list[int] = []
        self.cleanup_called = 0

    def get_runners(self) -> list[object]:
        """Return a copy of the current runner list.

        Returns:
            list[object]: Simulated runner instances.
        """
        return list(self._runners)

    def create_runners(self, num: int, metadata: object):  # noqa: ARG002
        """Record creation requests and extend the internal list.

        Args:
            num: Quantity of runners to create.
            metadata: Runner metadata (unused in tests).
        """
        self.created_args.append(num)
        # Simulate extending the runner list for visibility in follow-up checks
        if num > 0:
            self._runners.extend(object() for _ in range(num))

    def cleanup_runners(self):
        """Record that cleanup was invoked."""
        self.cleanup_called += 1


class _FakePlanner:
    """Planner client stub supplying flavor and pressure data for tests."""

    def __init__(
        self, flavor_min_pressure: int | None = None, stream_updates: list[float] | None = None
    ):
        """Initialize the planner stub with optional behavior.

        Args:
            flavor_min_pressure: Minimum pressure to report via `get_flavor`.
            stream_updates: Sequence of pressure values yielded by `stream_pressure`.
        """
        self._flavor_min_pressure = flavor_min_pressure
        self._stream_updates = stream_updates or []
        self.last_pressure_requested_for_flavor = ""

    def get_flavor(self, name: str):  # noqa: ARG002
        """Return a flavor namespace including `minimum_pressure`.

        Args:
            name: Flavor name (unused by the stub).

        Returns:
            types.SimpleNamespace: With fields `name` and `minimum_pressure`.
        """
        return SimpleNamespace(name="small", minimum_pressure=self._flavor_min_pressure)

    def get_pressure(self, name: str):
        """Return a pressure namespace with the latest configured value.

        Args:
            name: Flavor name whose pressure is requested.

        Returns:
            types.SimpleNamespace: With field `pressure` set to last update or 0.
        """
        self.last_pressure_requested_for_flavor = name
        # Return the last update by default if available, else 0
        value = self._stream_updates[-1] if self._stream_updates else 0
        return SimpleNamespace(pressure=value)

    def stream_pressure(self, name: str):  # noqa: ARG002
        """Yield pressure updates from the configured sequence.

        Args:
            name: Flavor name (unused by the stub).

        Yields:
            types.SimpleNamespace: Items with a `pressure` float value.
        """
        for p in self._stream_updates:
            yield SimpleNamespace(pressure=p)


def test_init_sets_minimum_pressure_from_flavor():
    """Test __init__ loads flavor and sets minimum pressure.

    Arrange: Planner returns flavor with minimum_pressure=3.
    Act: Construct PressureReconciler.
    Assert: Internal _min_pressure equals 3.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(flavor_min_pressure=(min_pressure := 3))
    cfg = PressureReconcilerConfig(flavor_name="small", poll_interval=10)

    reconciler = PressureReconciler(mgr, planner, cfg)

    assert reconciler._min_pressure == min_pressure  # noqa: SLF001


@pytest.mark.parametrize(
    "current_total, pressure, expected_create_nums",
    [
        (1, 2, [1]),
        (5, 4.0, []),
    ],
)
def test_handle_create_parametrized(current_total, pressure, expected_create_nums):
    """Test create handler: creates desired - current or no-ops.

    Arrange: Vary current-total and pressure.
    Act: Call _handle_create.
    Assert: create_runners call count/value matches expectation.
    """
    mgr = _FakeManager(runners_count=current_total)
    planner = _FakePlanner(flavor_min_pressure=None)
    cfg = PressureReconcilerConfig(flavor_name="small", poll_interval=10)

    reconciler = PressureReconciler(mgr, planner, cfg)
    reconciler._handle_create(pressure)

    assert mgr.created_args == expected_create_nums


@pytest.mark.parametrize(
    "current_total, reported_pressure, expected_create_nums",
    [
        (3, 2, []),
        (1, 4, [3]),
    ],
)
def test_handle_delete_parametrized(
    current_total,
    reported_pressure,
    expected_create_nums,
):
    """Test delete handler cleans up; creates when pressure > current.

    Arrange: Vary current-total and reported planner pressure.
    Act: Call _handle_delete; it will fetch pressure internally.
    Assert: cleanup_runners and create_runners usage match expectation.
    """
    mgr = _FakeManager(runners_count=current_total)
    planner = _FakePlanner(flavor_min_pressure=None, stream_updates=[reported_pressure])
    cfg = PressureReconcilerConfig(flavor_name="small", poll_interval=10)

    reconciler = PressureReconciler(mgr, planner, cfg)
    reconciler._handle_delete(reported_pressure)

    assert mgr.created_args == expected_create_nums


@pytest.mark.parametrize(
    "min_pressure, pressure, expected",
    [
        (5, 0.0, 5),
        (5, 4.9, 5),
        (5, 7.2, 7),
        (5, -3.0, 5),
        (None, 0.0, 0),
        (None, -1.0, 0),
    ],
)
def test_desired_total_parametrized(min_pressure: int | None, pressure: float, expected: int):
    """Test desired total uses max(int(pressure), minimum_pressure, 0).

    Arrange: Parameterized minimum_pressure and pressure values.
    Act: Call _desired_total_from_pressure.
    Assert: Result equals expected.
    """
    mgr = _FakeManager()
    planner = _FakePlanner(flavor_min_pressure=min_pressure)
    cfg = PressureReconcilerConfig(flavor_name="small", poll_interval=10)

    reconciler = PressureReconciler(mgr, planner, cfg)
    assert reconciler._desired_total_from_pressure(pressure) == expected
