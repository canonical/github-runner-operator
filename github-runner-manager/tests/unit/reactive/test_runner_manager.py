#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
from random import randint
from unittest.mock import MagicMock

import pytest

import github_runner_manager.reactive.process_manager
from github_runner_manager.configuration import UserInfo
from github_runner_manager.manager.runner_manager import (
    FlushMode,
    IssuedMetricEventsStats,
    RunnerInstance,
    RunnerManager,
)
from github_runner_manager.metrics.events import RunnerStart, RunnerStop
from github_runner_manager.reactive.runner_manager import reconcile
from github_runner_manager.reactive.types_ import QueueConfig, ReactiveProcessConfig

TEST_METRIC_EVENTS = {RunnerStart: 1, RunnerStop: 2}
TEST_DELETE_RUNNER_METRIC_EVENTS = {RunnerStart: 1, RunnerStop: 1}


@pytest.fixture(name="runner_manager")
def runner_manager_fixture() -> MagicMock:
    """Return a mock of the RunnerManager."""
    mock = MagicMock(spec=RunnerManager)
    mock.cleanup.return_value = TEST_METRIC_EVENTS
    mock.delete_runners.return_value = TEST_DELETE_RUNNER_METRIC_EVENTS
    return mock


@pytest.fixture(name="reactive_process_manager")
def reactive_process_manager_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Return a mock of the process manager."""
    reactive_process_manager = MagicMock(spec=github_runner_manager.reactive.process_manager)
    monkeypatch.setattr(
        "github_runner_manager.reactive.runner_manager.process_manager",
        reactive_process_manager,
    )
    reactive_process_manager.reconcile.side_effect = lambda *args, **kwargs: kwargs["quantity"]
    return reactive_process_manager


@pytest.fixture(name="reactive_process_config")
def reactive_process_config_fixture():
    """Return a mock of the ReactiveProcessConfig."""
    reactive_process_config = MagicMock(spec=ReactiveProcessConfig)
    reactive_process_config.queue = MagicMock(spec=QueueConfig)
    return reactive_process_config


@pytest.mark.parametrize(
    "runner_quantity, desired_quantity, expected_process_quantity",
    [
        pytest.param(5, 5, 0, id="zero processes to spawn"),
        pytest.param(5, 10, 5, id="5 processes to spawn"),
        pytest.param(5, 7, 2, id="2 processes to spawn"),
        pytest.param(0, 5, 5, id="no runners running"),
        pytest.param(0, 0, 0, id="zero quantity"),
    ],
)
def test_reconcile_positive_runner_diff(
    runner_quantity: int,
    desired_quantity: int,
    expected_process_quantity: int,
    runner_manager: MagicMock,
    reactive_process_manager: MagicMock,
    reactive_process_config: MagicMock,
    user_info: UserInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock the difference of amount of runners and desired quantity to be positive.
    act: Call reconcile.
    assert: The cleanup method of runner manager is called and the reconcile method of
        process manager is called with the expected quantity.
    """
    runner_manager.get_runners = MagicMock(
        return_value=(tuple(MagicMock(spec=RunnerInstance) for _ in range(runner_quantity)))
    )
    _set_queue_non_empty(monkeypatch)

    reconcile(desired_quantity, runner_manager, reactive_process_config, user_info)

    runner_manager.cleanup.assert_called_once()
    reactive_process_manager.reconcile.assert_called_once_with(
        quantity=expected_process_quantity,
        reactive_process_config=reactive_process_config,
        user=user_info,
    )


@pytest.mark.parametrize(
    "runner_quantity, desired_quantity, expected_number_of_runners_to_delete",
    [
        pytest.param(6, 5, 1, id="one additional runner"),
        pytest.param(8, 5, 3, id="multiple additional runners"),
        pytest.param(10, 0, 10, id="zero desired quantity"),
    ],
)
def test_reconcile_negative_runner_diff(
    runner_quantity: int,
    desired_quantity: int,
    expected_number_of_runners_to_delete: int,
    runner_manager: MagicMock,
    reactive_process_manager: MagicMock,
    reactive_process_config: MagicMock,
    user_info: UserInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock the difference of amount of runners and desired quantity to be negative.
    act: Call reconcile.
    assert: The additional amount of runners are deleted and the reconcile method of the
        process manager is called with zero quantity.
    """
    runner_manager.get_runners = MagicMock(
        return_value=(tuple(MagicMock(spec=RunnerInstance) for _ in range(runner_quantity)))
    )
    _set_queue_non_empty(monkeypatch)

    reconcile(desired_quantity, runner_manager, reactive_process_config, user_info)

    runner_manager.cleanup.assert_called_once()
    runner_manager.delete_runners.assert_called_once_with(expected_number_of_runners_to_delete)
    reactive_process_manager.reconcile.assert_called_once_with(
        quantity=0, reactive_process_config=reactive_process_config, user=user_info
    )


def test_reconcile_flushes_idle_runners_when_queue_is_empty(
    runner_manager: MagicMock,
    reactive_process_manager: MagicMock,
    reactive_process_config: MagicMock,
    user_info: UserInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock the dependencies and set the queue size to 0.
    act: Call reconcile with random quantity.
    assert: The flush_runners method of runner manager is called with FLUSH_IDLE mode.
    """
    quantity = randint(0, 10)
    _set_queue_empty(monkeypatch)

    reconcile(quantity, runner_manager, reactive_process_config, user_info)

    runner_manager.flush_runners.assert_called_once_with(FlushMode.FLUSH_IDLE)


@pytest.mark.usefixtures("reactive_process_manager")
@pytest.mark.parametrize(
    "runner_quantity, desired_quantity, cleanup_metric_stats, delete_metric_stats, "
    "expected_metrics",
    [
        pytest.param(
            1,
            5,
            (default_cleanup_stats := {RunnerStart: 1, RunnerStop: 3}),
            (default_delete_stats := {RunnerStart: 3, RunnerStop: 4}),
            {RunnerStart: 1, RunnerStop: 3},
            id="positive runner diff returns cleanup stats",
        ),
        pytest.param(
            1,
            5,
            default_cleanup_stats,
            dict(),
            default_cleanup_stats,
            id="positive runner diff with empty delete stats",
        ),
        pytest.param(
            1,
            5,
            dict(),
            default_delete_stats,
            dict(),
            id="positive runner diff with empty cleanup stats",
        ),
        pytest.param(1, 5, dict(), dict(), dict(), id="positive runner diff with empty stats"),
        pytest.param(
            0,
            0,
            default_cleanup_stats,
            default_delete_stats,
            default_cleanup_stats,
            id="zero runner diff returns cleanup stats",
        ),
        pytest.param(
            0,
            0,
            default_cleanup_stats,
            dict(),
            default_cleanup_stats,
            id="zero runner diff with empty delete stats",
        ),
        pytest.param(
            0,
            0,
            dict(),
            default_delete_stats,
            dict(),
            id="zero runner diff with empty cleanup stats",
        ),
        pytest.param(0, 0, dict(), dict(), dict(), id="zero runner diff with empty stats"),
        pytest.param(
            5,
            1,
            {RunnerStart: 1, RunnerStop: 3},
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 4, RunnerStop: 7},
            id="negative runner diff returns merged stats",
        ),
        pytest.param(
            5,
            1,
            default_cleanup_stats,
            dict(),
            default_cleanup_stats,
            id="negative runner diff with empty delete stats",
        ),
        pytest.param(
            5,
            1,
            dict(),
            default_delete_stats,
            default_delete_stats,
            id="negative runner diff with empty cleanup stats",
        ),
        pytest.param(5, 1, dict(), dict(), dict(), id="negative runner diff with empty stats"),
        pytest.param(
            5,
            1,
            {RunnerStart: 3},
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 6, RunnerStop: 4},
            id="cleanup stats without RunnerStop",
        ),
        pytest.param(
            5,
            1,
            {RunnerStop: 3},
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 3, RunnerStop: 7},
            id="cleanup stats without RunnerStart",
        ),
        pytest.param(
            5,
            1,
            {RunnerStart: 3},
            {RunnerStop: 4},
            {RunnerStart: 3, RunnerStop: 4},
            id="delete stats without RunnerStart",
        ),
        pytest.param(
            5,
            1,
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 4},
            {RunnerStart: 7, RunnerStop: 4},
            id="delete stats without RunnerStop",
        ),
    ],
)
def test_reconcile_returns_issued_metrics(
    runner_quantity: int,
    desired_quantity: int,
    cleanup_metric_stats: IssuedMetricEventsStats,
    delete_metric_stats: IssuedMetricEventsStats,
    expected_metrics: IssuedMetricEventsStats,
    runner_manager: MagicMock,
    reactive_process_config: MagicMock,
    user_info: UserInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock different stats and runner diff combinations and an empty queue.
    act: Call reconcile.
    assert: The returned metrics are as expected.
    """
    runner_manager.get_runners = MagicMock(
        return_value=(tuple(MagicMock(spec=RunnerInstance) for _ in range(runner_quantity)))
    )
    runner_manager.cleanup.return_value = cleanup_metric_stats
    runner_manager.delete_runners.return_value = delete_metric_stats

    _set_queue_non_empty(monkeypatch)

    result = reconcile(desired_quantity, runner_manager, reactive_process_config, user_info)

    assert result.metric_stats == expected_metrics


@pytest.mark.usefixtures("reactive_process_manager")
@pytest.mark.parametrize(
    "runner_quantity, desired_quantity, cleanup_metric_stats, delete_metric_stats, "
    "flush_metric_stats, expected_metrics",
    [
        pytest.param(
            1,
            5,
            (default_cleanup_stats := {RunnerStart: 1, RunnerStop: 3}),
            (default_delete_stats := {RunnerStart: 3, RunnerStop: 4}),
            (default_flush_stats := {RunnerStart: 5, RunnerStop: 6}),
            {RunnerStart: 6, RunnerStop: 9},
            id="positive runner diff returns cleanup + flush stats",
        ),
        pytest.param(
            1,
            5,
            default_cleanup_stats,
            default_delete_stats,
            dict(),
            default_cleanup_stats,
            id="positive runner diff with empty flush stats",
        ),
        pytest.param(
            1,
            5,
            dict(),
            default_delete_stats,
            default_flush_stats,
            default_flush_stats,
            id="positive runner diff with empty cleanup stats",
        ),
        pytest.param(
            1, 5, dict(), dict(), dict(), dict(), id="positive runner diff with empty stats"
        ),
        pytest.param(
            0,
            0,
            default_cleanup_stats,
            default_delete_stats,
            default_flush_stats,
            {RunnerStart: 6, RunnerStop: 9},
            id="zero runner diff returns cleanup + flush stats",
        ),
        pytest.param(
            0,
            0,
            default_cleanup_stats,
            default_delete_stats,
            dict(),
            default_cleanup_stats,
            id="zero runner diff with empty flush stats",
        ),
        pytest.param(
            0,
            0,
            dict(),
            default_delete_stats,
            default_flush_stats,
            default_flush_stats,
            id="zero runner diff with empty cleanup stats",
        ),
        pytest.param(0, 0, dict(), dict(), dict(), dict(), id="zero runner diff with empty stats"),
        pytest.param(
            5,
            1,
            {RunnerStart: 1, RunnerStop: 3},
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 5, RunnerStop: 6},
            {RunnerStart: 9, RunnerStop: 13},
            id="negative runner diff returns merged stats",
        ),
        pytest.param(
            5,
            1,
            {RunnerStart: 1, RunnerStop: 3},
            {RunnerStart: 3, RunnerStop: 4},
            dict(),
            {RunnerStart: 4, RunnerStop: 7},
            id="negative runner diff with empty flush stats",
        ),
        pytest.param(
            5,
            1,
            dict(),
            {RunnerStart: 1, RunnerStop: 3},
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 4, RunnerStop: 7},
            id="negative runner diff with empty cleanup stats",
        ),
        pytest.param(
            5,
            1,
            {RunnerStart: 1, RunnerStop: 3},
            dict(),
            {RunnerStart: 3, RunnerStop: 4},
            {RunnerStart: 4, RunnerStop: 7},
            id="negative runner diff with empty delete stats",
        ),
        pytest.param(
            5, 1, dict(), dict(), dict(), dict(), id="negative runner diff with empty stats"
        ),
    ],
)
def test_reconcile_empty_queue_returns_issued_metrics(
    runner_quantity: int,
    desired_quantity: int,
    cleanup_metric_stats: IssuedMetricEventsStats,
    delete_metric_stats: IssuedMetricEventsStats,
    flush_metric_stats: IssuedMetricEventsStats,
    expected_metrics: IssuedMetricEventsStats,
    runner_manager: MagicMock,
    reactive_process_config: MagicMock,
    user_info: UserInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock different stats and runner diff combinations and an empty queue.
    act: Call reconcile.
    assert: The returned metrics are as expected.
    """
    runner_manager.get_runners = MagicMock(
        return_value=(tuple(MagicMock(spec=RunnerInstance) for _ in range(runner_quantity)))
    )
    runner_manager.cleanup.return_value = cleanup_metric_stats
    runner_manager.delete_runners.return_value = delete_metric_stats
    runner_manager.flush_runners.return_value = flush_metric_stats

    _set_queue_empty(monkeypatch)

    result = reconcile(desired_quantity, runner_manager, reactive_process_config, user_info)

    assert result.metric_stats == expected_metrics


def _set_queue_non_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the queue size to a random value between 1 and 10.

    Args:
        monkeypatch: The pytest monkeypatch fixture used to patch the get_queue_size function.
    """
    monkeypatch.setattr(
        "github_runner_manager.reactive.runner_manager.get_queue_size",
        lambda _: randint(1, 10),
    )


def _set_queue_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the queue size to zero.

    Args:
        monkeypatch: The pytest monkeypatch fixture used to patch the get_queue_size function.
    """
    monkeypatch.setattr(
        "github_runner_manager.reactive.runner_manager.get_queue_size",
        lambda _: 0,
    )
