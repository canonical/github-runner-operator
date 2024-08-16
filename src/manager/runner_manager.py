# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for managing the GitHub self-hosted runners hosted on cloud instances."""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from multiprocessing import Pool
from typing import Iterator, Sequence, Type, cast

from charm_state import GithubPath
from errors import GithubMetricsError, RunnerCreateError
from github_type import SelfHostedRunner
from manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    HealthState,
    InstanceId,
)
from manager.github_runner_manager import GithubRunnerManager, GithubRunnerState
from metrics import events as metric_events
from metrics import github as github_metrics
from metrics import runner as runner_metrics
from metrics.runner import RunnerMetrics

logger = logging.getLogger(__name__)

IssuedMetricEventsStats = dict[Type[metric_events.Event], int]


class FlushMode(Enum):
    """Strategy for flushing runners.

    Attributes:
        FLUSH_IDLE: Flush idle runners.
        FLUSH_BUSY: Flush busy runners.
    """

    FLUSH_IDLE = auto()
    FLUSH_BUSY = auto()


@dataclass
class RunnerInstance:
    """Represents an instance of runner.

    Attributes:
        name: Full name of the runner. Managed by the cloud runner manager.
        instance_id: ID of the runner. Managed by the runner manager.
        health: The health state of the runner.
        github_state: State on github.
        cloud_state: State on cloud.
    """

    name: str
    instance_id: InstanceId
    health: HealthState
    github_state: GithubRunnerState | None
    cloud_state: CloudRunnerState

    def __init__(self, cloud_instance: CloudRunnerInstance, github_info: SelfHostedRunner | None):
        """Construct an instance.

        Args:
            cloud_instance: Information on the cloud instance.
            github_info: Information on the GitHub of the runner.
        """
        self.name = cloud_instance.name
        self.instance_id = cloud_instance.instance_id
        self.health = cloud_instance.health
        self.github_state = (
            GithubRunnerState.from_runner(github_info) if github_info is not None else None
        )
        self.cloud_state = cloud_instance.state


@dataclass
class RunnerManagerConfig:
    """Configuration for the runner manager.

    Attributes:
        token: GitHub personal access token to query GitHub API.
        path: Path to GitHub repository or organization to registry the runners.
    """

    token: str
    path: GithubPath


class RunnerManager:
    """Manage the runners."""

    def __init__(self, cloud_runner_manager: CloudRunnerManager, config: RunnerManagerConfig):
        """Construct the object.

        Args:
            cloud_runner_manager: For managing the cloud instance of the runner.
            config: Configuration of this class.
        """
        self._config = config
        self._cloud = cloud_runner_manager
        self.name_prefix = self._cloud.name_prefix
        self._github = GithubRunnerManager(
            prefix=self.name_prefix, token=self._config.token, path=self._config.path
        )

    def create_runners(self, num: int) -> tuple[InstanceId]:
        """Create runners.

        Args:
            num: Number of runners to create.

        Returns:
            List of instance ID of the runners.
        """
        logger.info("Creating %s runners", num)
        registration_token = self._github.get_registration_token()

        create_runner_args = [
            RunnerManager._CreateRunnerArgs(self._cloud, registration_token) for _ in range(num)
        ]
        instance_id_list = []
        with Pool(processes=min(num, 10)) as pool:
            jobs = pool.imap_unordered(
                func=RunnerManager._create_runner, iterable=create_runner_args
            )
            for _ in range(num):
                try:
                    instance_id = next(jobs)
                except RunnerCreateError:
                    logger.exception("Failed to spawn a runner.")
                except StopIteration:
                    break
                else:
                    instance_id_list.append(instance_id)
        return tuple(instance_id_list)

    def get_runners(
        self,
        github_states: Sequence[GithubRunnerState] | None = None,
        cloud_states: Sequence[CloudRunnerState] | None = None,
    ) -> tuple[RunnerInstance]:
        """Get information on runner filter by state.

        Only runners that has cloud instance are returned.

        Args:
            github_states: Filter for the runners with these github states. If None all
                states will be included.
            cloud_states: Filter for the runners with these cloud states. If None all states
                will be included.

        Returns:
            Information on the runners.
        """
        logger.info("Getting runners...")
        github_infos = self._github.get_runners(github_states)
        cloud_infos = self._cloud.get_runners(cloud_states)
        github_infos_map = {info.name: info for info in github_infos}
        cloud_infos_map = {info.name: info for info in cloud_infos}
        logger.info(
            "Found following runners: %s", cloud_infos_map.keys() | github_infos_map.keys()
        )

        runner_names = cloud_infos_map.keys() & github_infos_map.keys()
        cloud_only = cloud_infos_map.keys() - runner_names
        github_only = github_infos_map.keys() - runner_names
        if cloud_only:
            logger.warning(
                "Found runner instance on cloud but not registered on GitHub: %s", cloud_only
            )
        if github_only:
            logger.warning(
                "Found self-hosted runner on GitHub but no matching runner instance on cloud: %s",
                github_only,
            )

        runner_instances: list[RunnerInstance] = [
            RunnerInstance(
                cloud_infos_map[name], github_infos_map[name] if name in github_infos_map else None
            )
            for name in cloud_infos_map.keys()
        ]
        if cloud_states is not None:
            runner_instances = [
                runner for runner in runner_instances if runner.cloud_state in cloud_states
            ]
        if github_states is not None:
            runner_instances = [
                runner
                for runner in runner_instances
                if runner.github_state is not None and runner.github_state in github_states
            ]
        return cast(tuple[RunnerInstance], tuple(runner_instances))

    def delete_runners(self, num: int) -> IssuedMetricEventsStats:
        """Delete runners.

        Args:
            num: The number of runner to delete.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        logger.info("Deleting %s number of runners", num)
        runners_list = self.get_runners()[:num]
        runner_names = [runner.name for runner in runners_list]
        logger.info("Deleting runners: %s", runner_names)
        remove_token = self._github.get_removal_token()
        return self._delete_runners(runners=runners_list, remove_token=remove_token)

    def flush_runners(
        self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE
    ) -> IssuedMetricEventsStats:
        """Delete runners according to state.

        Args:
            flush_mode: The type of runners affect by the deletion.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        match flush_mode:
            case FlushMode.FLUSH_IDLE:
                logger.info("Flushing idle runners...")
            case FlushMode.FLUSH_BUSY:
                logger.info("Flushing idle and busy runners...")
            case _:
                logger.critical(
                    "Unknown flush mode %s encountered, contact developers", flush_mode
                )

        states = [GithubRunnerState.IDLE]
        if flush_mode == FlushMode.FLUSH_BUSY:
            states.append(GithubRunnerState.BUSY)

        runners_list = self.get_runners(github_states=states)
        runner_names = [runner.name for runner in runners_list]
        logger.info("Flushing runners: %s", runner_names)
        remove_token = self._github.get_removal_token()
        return self._delete_runners(runners=runners_list, remove_token=remove_token)

    def cleanup(self) -> IssuedMetricEventsStats:
        """Run cleanup of the runners and other resources.

        Returns:
            Stats on metrics events issued during the cleanup of runners.
        """
        self._github.delete_runners([GithubRunnerState.OFFLINE])
        remove_token = self._github.get_removal_token()
        deleted_runner_metrics = self._cloud.cleanup(remove_token)
        return self._issue_runner_metrics(metrics=deleted_runner_metrics)

    def _delete_runners(
        self, runners: Sequence[RunnerInstance], remove_token: str
    ) -> IssuedMetricEventsStats:
        """Delete list of runners.

        Args:
            runners: The runners to delete.
            remove_token: The token for removing self-hosted runners.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        runner_metrics_list = []
        for runner in runners:
            deleted_runner_metrics = self._cloud.delete_runner(
                instance_id=runner.instance_id, remove_token=remove_token
            )
            if deleted_runner_metrics is not None:
                runner_metrics_list.append(deleted_runner_metrics)
        return self._issue_runner_metrics(metrics=iter(runner_metrics_list))

    def _issue_runner_metrics(self, metrics: Iterator[RunnerMetrics]) -> IssuedMetricEventsStats:
        """Issue runner metrics.

        Args:
            metrics: Runner metrics to issue.

        Returns:
            Stats on runner metrics issued.
        """
        total_stats: IssuedMetricEventsStats = {}

        for extracted_metrics in metrics:
            try:
                job_metrics = github_metrics.job(
                    github_client=self._github.github,
                    pre_job_metrics=extracted_metrics.pre_job,
                    runner_name=extracted_metrics.runner_name,
                )
            except GithubMetricsError:
                logger.exception(
                    "Failed to calculate job metrics for %s", extracted_metrics.runner_name
                )
                job_metrics = None

            issued_events = runner_metrics.issue_events(
                runner_metrics=extracted_metrics,
                job_metrics=job_metrics,
                flavor=self.name_prefix,
            )

            for event_type in issued_events:
                total_stats[event_type] = total_stats.get(event_type, 0) + 1

        return total_stats

    @dataclass
    class _CreateRunnerArgs:
        """Arguments for the _create_runner function.

        Attrs:
            cloud_runner_manager: For managing the cloud instance of the runner.
            registration_token: The GitHub provided-token for registering runners.
        """

        cloud_runner_manager: CloudRunnerManager
        registration_token: str

    @staticmethod
    def _create_runner(args: _CreateRunnerArgs) -> InstanceId:
        """Create a single runner.

        This is a staticmethod for usage with multiprocess.Pool.

        Args:
            args: The arguments.

        Returns:
            The instance ID of the runner created.
        """
        return args.cloud_runner_manager.create_runner(registration_token=args.registration_token)
