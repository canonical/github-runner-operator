#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for reconciling amount of runner and reactive runner processes."""
import logging
from dataclasses import dataclass

from github_runner_manager.configuration import UserInfo
from github_runner_manager.manager.runner_manager import (
    FlushMode,
    IssuedMetricEventsStats,
    RunnerManager,
)
from github_runner_manager.platform.github_provider import PlatformRunnerState
from github_runner_manager.reactive import process_manager
from github_runner_manager.reactive.consumer import get_queue_size
from github_runner_manager.reactive.types_ import ReactiveProcessConfig

logger = logging.getLogger(__name__)


@dataclass
class ReconcileResult:
    """The result of the reconciliation.

    Attributes:
        processes_diff: The number of reactive processes created/removed.
        metric_stats: The stats of the issued metric events
    """

    processes_diff: int
    metric_stats: IssuedMetricEventsStats


def reconcile(
    expected_quantity: int,
    runner_manager: RunnerManager,
    reactive_process_config: ReactiveProcessConfig,
    user: UserInfo,
) -> ReconcileResult:
    """Reconcile runners reactively.

    The reconciliation attempts to make the following equation true:
        quantity_of_current_runners + amount_of_reactive_processes_consuming_jobs
            == expected_quantity

    A few examples:

    1. If there are 5 runners and 5 reactive processes and the quantity is 10,
        no action is taken.
    2. If there are 5 runners and 5 reactive processes and the quantity is 15,
        5 reactive processes are created.
    3. If there are 5 runners and 5 reactive processes and quantity is 7,
        3 reactive processes are killed.
    4. If there are 5 runners and 5 reactive processes and quantity is 5,
        all reactive processes are killed.
    5. If there are 5 runners and 5 reactive processes and quantity is 4,
        1 runner is killed and all reactive processes are killed.


    So if the quantity is equal to the sum of the current runners and reactive processes,
    no action is taken,

    If the quantity is greater than the sum of the current
    runners and reactive processes, additional reactive processes are created.

    If the quantity is greater than or equal to the quantity of the current runners,
    but less than the sum of the current runners and reactive processes,
    additional reactive processes will be killed.

    If the quantity is less than the sum of the current runners,
    additional runners are killed and all reactive processes are killed.

    In addition to this behaviour, reconciliation also checks the queue at the start and
    removes all idle runners if the queue is empty, to ensure that
    no idle runners are left behind if there are no new jobs.

    Args:
        expected_quantity: Number of intended amount of runners + reactive processes.
        runner_manager: The runner manager to interact with current running runners.
        reactive_process_config: The reactive runner config.
        user: The user to run the reactive process.

    Returns:
        The number of reactive processes created. If negative, its absolute value is equal
        to the number of processes killed.
    """
    cleanup_metric_stats = runner_manager.cleanup()
    flush_metric_stats = {}
    delete_metric_stats = {}

    if get_queue_size(reactive_process_config.queue) == 0:
        logger.info("Reactive reconcile. Flushing on empty queue")
        flush_metric_stats = runner_manager.flush_runners(FlushMode.FLUSH_IDLE)

    # Only count runners which are online on GitHub to prevent machines to be just in
    # construction to be counted and then killed immediately by the process manager.
    runners = runner_manager.get_runners(
        github_states=[PlatformRunnerState.IDLE, PlatformRunnerState.BUSY]
    )
    runner_diff = expected_quantity - len(runners)

    if runner_diff >= 0:
        process_quantity = runner_diff
    else:
        delete_metric_stats = runner_manager.delete_runners(-runner_diff)
        process_quantity = 0

    metric_stats = {
        event_name: delete_metric_stats.get(event_name, 0)
        + cleanup_metric_stats.get(event_name, 0)
        + flush_metric_stats.get(event_name, 0)
        for event_name in set(delete_metric_stats)
        | set(cleanup_metric_stats)
        | set(flush_metric_stats)
    }

    processes_created = process_manager.reconcile(
        quantity=process_quantity,
        reactive_process_config=reactive_process_config,
        user=user,
    )

    return ReconcileResult(processes_diff=processes_created, metric_stats=metric_stats)
