# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for scaling the runners amount."""

import logging
import time
from typing import TypedDict

from errors import IssueMetricEventError, MissingServerConfigError
from manager.cloud_runner_manager import HealthState
from manager.github_runner_manager import GitHubRunnerState
from manager.runner_manager import FlushMode, RunnerManager
from metrics import events as metric_events

logger = logging.getLogger(__name__)


class RunnerInfo(TypedDict):
    """Information on the runners.

    Attributes:
        online: The number of runner in online state.
        offline: The number of runner in offline state.
        unknown: The number of runner in unknown state.
        runners: The names of the online runners.
    """

    online: int
    offline: int
    unknown: int
    runners: tuple[str, ...]


class RunnerScaler:
    """Manage the reconcile of runners."""

    def __init__(self, runner_manager: RunnerManager):
        """Construct the object.

        Args:
            runner_manager: The RunnerManager to perform runner reconcile.
        """
        self._manager = runner_manager

    def get_runner_info(self) -> RunnerInfo:
        """Get information on the runners.

        Returns:
            The information on the runners.
        """
        runner_list = self._manager.get_runners()
        online = 0
        offline = 0
        unknown = 0
        online_runners = []
        for runner in runner_list:
            match runner.github_state:
                case GitHubRunnerState.BUSY:
                    online += 1
                    online_runners.append(runner.name)
                case GitHubRunnerState.IDLE:
                    online += 1
                    online_runners.append(runner.name)
                case GitHubRunnerState.OFFLINE:
                    offline += 1
                case _:
                    unknown += 1
        return RunnerInfo(
            online=online, offline=offline, unknown=unknown, runners=tuple(online_runners)
        )

    def flush(self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE) -> None:
        """Flush the runners.

        Args:
            flush_mode: Determines the types of runner to be flushed.

        Returns:
            Number of runners flushed.
        """
        metric_stats = self._manager.cleanup()
        delete_metric_stats = self._manager.delete_runners(flush_mode=flush_mode)
        metric_stats = {
            delete_metric_stats.get(event_name, 0) + metric_stats.get(event_name, 0)
            for event_name in set(delete_metric_stats) | set(metric_stats)
        }
        return metric_stats.get(metric_events.RunnerStop, 0)

    def reconcile(self, num_of_runner: int) -> int:
        """Reconcile the quantity of runners.

        Args:
            num_of_runner: The number of intended runners.

        Returns:
            The Change in number of runners.
        """
        logger.info("Start reconcile to %s runner", num_of_runner)

        start_timestamp = time.time()
        delete_metric_stats = None
        metric_stats = self._manager.cleanup()
        runners = self._manager.get_runners()
        current_num = len(runners)
        logger.info("Reconcile runners from %s to %s", current_num, num_of_runner)
        runner_diff = num_of_runner - current_num
        if runner_diff > 0:
            try:
                self._manager.create_runners(runner_diff)
            except MissingServerConfigError:
                logging.exception(
                    "Unable to spawn runner due to missing server configuration, such as, image."
                )
        elif runner_diff < 0:
            delete_metric_stats = self._manager.delete_runners(-runner_diff)
        else:
            logger.info("No changes to the number of runners.")
        end_timestamp = time.time()

        # Merge the two metric stats.
        if delete_metric_stats is not None:
            metric_stats = {
                delete_metric_stats.get(event_name, 0) + metric_stats.get(event_name, 0)
                for event_name in set(delete_metric_stats) | set(metric_stats)
            }

        runner_list = self._manager.get_runners()
        idle_runners = [
            runner for runner in runner_list if runner.github_state == GitHubRunnerState.IDLE
        ]
        offline_healthy_runners = [
            runner
            for runner in runner_list
            if runner.github_state == GitHubRunnerState.OFFLINE
            and runner.health == HealthState.HEALTHY
        ]

        try:
            metric_events.issue_event(
                metric_events.Reconciliation(
                    timestamp=time.time(),
                    flavor=self._manager.name_prefix,
                    crashed_runners=metric_stats.get(metric_events.RunnerStart, 0)
                    - metric_stats.get(metric_events.RunnerStop, 0),
                    idle_runners=len(set(idle_runners) | set(offline_healthy_runners)),
                    duration=end_timestamp - start_timestamp,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue Reconciliation metric")

        return runner_diff
