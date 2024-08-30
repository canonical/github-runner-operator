# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for scaling the runners amount."""

import logging
import time
from dataclasses import dataclass

from pydantic import MongoDsn

import reactive.runner_manager as reactive_runner_manager
from charm_state import ReactiveConfig
from errors import IssueMetricEventError, MissingServerConfigError
from manager.cloud_runner_manager import HealthState
from manager.github_runner_manager import GitHubRunnerState
from manager.runner_manager import FlushMode, RunnerManager
from metrics import events as metric_events

logger = logging.getLogger(__name__)


@dataclass
class RunnerInfo:
    """Information on the runners.

    Attributes:
        online: The number of runner in online state.
        busy: The number of the runner in busy state.
        offline: The number of runner in offline state.
        unknown: The number of runner in unknown state.
        runners: The names of the online runners.
        busy_runners: The names of the busy runners.
    """

    online: int
    busy: int
    offline: int
    unknown: int
    runners: tuple[str, ...]
    busy_runners: tuple[str, ...]


class RunnerScaler:
    """Manage the reconcile of runners."""

    def __init__(self, runner_manager: RunnerManager, reactive_config: ReactiveConfig | None):
        """Construct the object.

        Args:
            runner_manager: The RunnerManager to perform runner reconcile.
            reactive_config: Reactive runner configuration.
        """
        self._manager = runner_manager
        self._reactive_config = reactive_config

    def get_runner_info(self) -> RunnerInfo:
        """Get information on the runners.

        Returns:
            The information on the runners.
        """
        runner_list = self._manager.get_runners()
        online = 0
        busy = 0
        offline = 0
        unknown = 0
        online_runners = []
        busy_runners = []
        for runner in runner_list:
            match runner.github_state:
                case GitHubRunnerState.BUSY:
                    online += 1
                    online_runners.append(runner.name)
                    busy += 1
                    busy_runners.append(runner.name)
                case GitHubRunnerState.IDLE:
                    online += 1
                    online_runners.append(runner.name)
                case GitHubRunnerState.OFFLINE:
                    offline += 1
                case _:
                    unknown += 1
        return RunnerInfo(
            online=online,
            busy=busy,
            offline=offline,
            unknown=unknown,
            runners=tuple(online_runners),
            busy_runners=tuple(busy_runners),
        )

    def flush(self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE) -> int:
        """Flush the runners.

        Args:
            flush_mode: Determines the types of runner to be flushed.

        Returns:
            Number of runners flushed.
        """
        metric_stats = self._manager.cleanup()
        delete_metric_stats = self._manager.flush_runners(flush_mode=flush_mode)
        events = set(delete_metric_stats.keys()) | set(metric_stats.keys())
        metric_stats = {
            event_name: delete_metric_stats.get(event_name, 0) + metric_stats.get(event_name, 0)
            for event_name in events
        }
        return metric_stats.get(metric_events.RunnerStop, 0)

    def reconcile(self, quantity: int) -> int:
        """Reconcile the quantity of runners.

        Args:
            quantity: The number of intended runners.

        Returns:
            The Change in number of runners.
        """
        logger.info("Start reconcile to %s runner", quantity)

        if self._reactive_config is not None:
            logger.info("Reactive configuration detected, going into experimental reactive mode.")
            return self._reconcile_reactive(quantity, self._reactive_config.mq_uri)

        start_timestamp = time.time()
        delete_metric_stats = None
        metric_stats = self._manager.cleanup()
        runners = self._manager.get_runners()
        current_num = len(runners)
        logger.info("Reconcile runners from %s to %s", current_num, quantity)
        runner_diff = quantity - current_num
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
                event_name: delete_metric_stats.get(event_name, 0)
                + metric_stats.get(event_name, 0)
                for event_name in set(delete_metric_stats) | set(metric_stats)
            }

        runner_list = self._manager.get_runners()
        busy_runners = [
            runner for runner in runner_list if runner.github_state == GitHubRunnerState.BUSY
        ]
        idle_runners = [
            runner for runner in runner_list if runner.github_state == GitHubRunnerState.IDLE
        ]
        offline_healthy_runners = [
            runner
            for runner in runner_list
            if runner.github_state == GitHubRunnerState.OFFLINE
            and runner.health == HealthState.HEALTHY
        ]
        unhealthy_runners = [
            runner for runner in runner_list if runner.health == HealthState.UNHEALTHY or runner.health == HealthState.UNKNOWN
        ]
        logger.info("Found %s busy runners: %s", len(busy_runners), busy_runners)
        logger.info("Found %s idle runners: %s", len(idle_runners), idle_runners)
        logger.info(
            "Found %s offline runners that are healthy: %s",
            len(offline_healthy_runners),
            offline_healthy_runners,
        )
        logger.info("Found %s unhealthy runners: %s", len(unhealthy_runners), unhealthy_runners)

        try:
            available_runners = set(runner.name for runner in idle_runners) | set(
                runner.name for runner in offline_healthy_runners
            )
            logger.info(
                "Current available runners (idle + healthy offline): %s", available_runners
            )
            metric_events.issue_event(
                metric_events.Reconciliation(
                    timestamp=time.time(),
                    flavor=self._manager.manager_name,
                    crashed_runners=metric_stats.get(metric_events.RunnerStart, 0)
                    - metric_stats.get(metric_events.RunnerStop, 0),
                    idle_runners=len(available_runners),
                    duration=end_timestamp - start_timestamp,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue Reconciliation metric")

        return runner_diff

    def _reconcile_reactive(self, quantity: int, mq_uri: MongoDsn) -> int:
        """Reconcile runners reactively.

        Args:
            quantity: Number of intended runners.
            mq_uri: The URI of the MQ to use to spawn runners reactively.

        Returns:
            The difference between intended runners and actual runners. In reactive mode
            this number is never negative as additional processes should terminate after a timeout.
        """
        logger.info("Reactive mode is experimental and not yet fully implemented.")
        return reactive_runner_manager.reconcile(
            quantity=quantity,
            mq_uri=mq_uri,
            queue_name=self._manager.manager_name,
        )
