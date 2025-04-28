# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing the GitHub self-hosted runners hosted on cloud instances."""

import copy
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from multiprocessing import Pool
from typing import Iterator, Sequence, Type, cast

from github_runner_manager import constants
from github_runner_manager.errors import GithubMetricsError, PlatformApiError, RunnerError
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    HealthState,
)
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics import github as github_metrics
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.platform.platform_provider import (
    PlatformProvider,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import SelfHostedRunner

logger = logging.getLogger(__name__)

# After a runner is created, there will be as many health checks as
# elements in this variable. The elements in the tuple represent
# the time waiting before each health check against the platform provider.
RUNNER_CREATION_WAITING_TIMES = (60, 60, 120, 240, 480)

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
        metadata: Metadata for the runner.
        health: The health state of the runner.
        github_state: State on github.
        cloud_state: State on cloud.
    """

    name: str
    instance_id: InstanceID
    metadata: RunnerMetadata
    health: HealthState
    github_state: PlatformRunnerState | None
    cloud_state: CloudRunnerState

    def __init__(self, cloud_instance: CloudRunnerInstance, github_info: SelfHostedRunner | None):
        """Construct an instance.

        Args:
            cloud_instance: Information on the cloud instance.
            github_info: Information on the GitHub of the runner.
        """
        self.name = cloud_instance.name
        self.instance_id = cloud_instance.instance_id
        self.metadata = cloud_instance.metadata
        self.health = cloud_instance.health
        self.github_state = (
            PlatformRunnerState.from_runner(github_info) if github_info is not None else None
        )
        self.cloud_state = cloud_instance.state


class RunnerManager:
    """Manage the runners.

    Attributes:
        manager_name: A name to identify this manager.
        name_prefix: The name prefix of the runners.
    """

    def __init__(
        self,
        manager_name: str,
        platform_provider: PlatformProvider,
        cloud_runner_manager: CloudRunnerManager,
        labels: list[str],
    ):
        """Construct the object.

        Args:
            manager_name: Name of the manager.
            platform_provider: Platform provider.
            cloud_runner_manager: For managing the cloud instance of the runner.
            labels: Labels for the runners created.
        """
        self.manager_name = manager_name
        self._cloud = cloud_runner_manager
        self.name_prefix = self._cloud.name_prefix
        self._platform: PlatformProvider = platform_provider
        self._labels = labels

    def create_runners(
        self, num: int, metadata: RunnerMetadata, reactive: bool = False
    ) -> tuple[InstanceID, ...]:
        """Create runners.

        Args:
            num: Number of runners to create.
            metadata: Metadata information for the runner.
            reactive: If the runner is reactive.

        Returns:
            List of instance ID of the runners.
        """
        logger.info("Creating %s runners", num)

        labels = list(self._labels)
        # This labels are added by default by the github agent, but with JIT tokens
        # we have to add them manually.
        labels += constants.GITHUB_DEFAULT_LABELS
        create_runner_args = [
            RunnerManager._CreateRunnerArgs(
                cloud_runner_manager=self._cloud,
                platform_provider=self._platform,
                # The metadata may be manipulated when creating the runner, as the platform may
                # assign for example the id of the runner if it was not provided.
                metadata=copy.copy(metadata),
                labels=labels,
                reactive=reactive,
            )
            for _ in range(num)
        ]
        return RunnerManager._spawn_runners(create_runner_args)

    def get_runners(
        self,
        github_states: Sequence[PlatformRunnerState] | None = None,
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
        github_infos = self._platform.get_runners(github_states)
        cloud_infos = self._cloud.get_runners(cloud_states)
        github_infos_map = {info.instance_id.name: info for info in github_infos}
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
        remove_token = self._platform.get_removal_token()
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

        busy = False
        if flush_mode == FlushMode.FLUSH_BUSY:
            busy = True
        remove_token = self._platform.get_removal_token()
        stats = self._cloud.flush_runners(remove_token, busy)
        return self._issue_runner_metrics(metrics=stats)

    def cleanup(self) -> IssuedMetricEventsStats:
        """Run cleanup of the runners and other resources.

        Returns:
            Stats on metrics events issued during the cleanup of runners.
        """
        self._cleanup_github_offline_runners()
        remove_token = self._platform.get_removal_token()
        deleted_runner_metrics = self._cloud.cleanup(remove_token)
        return self._issue_runner_metrics(metrics=deleted_runner_metrics)

    def _cleanup_github_offline_runners(self) -> None:
        """Run cleanup of github runners in offline state."""
        # RunnerManager.get_runners only get runners in the cloud provider, which can be
        # misleading. Pending to tackle and put the logic of this function to get_runners
        # and in the RunnerInstance.

        # For non-reactive runners, delete all offline runners. There are small
        # race conditions, as runners could be busy, for example in the case of a network restart
        # or a reboot of the machine.

        # For reactive runners, runners can be in CREATED state, meaning that the reactive process
        # is creating them. Same situation in ACTIVE and HEALTHY state, where the
        # reactive runner can be running the first steps of the startup (and cloud init script)
        # before running the GitHub agent.
        cloud_instances = self.get_runners()
        cloud_instances_map = {
            cloud_instance.instance_id: cloud_instance for cloud_instance in cloud_instances
        }

        github_runners_offline = self._platform.get_runners([PlatformRunnerState.OFFLINE])
        github_runners_to_delete = []
        for github_runner in github_runners_offline:
            # Delete all non-reactive runners
            if not github_runner.instance_id.reactive:
                github_runners_to_delete.append(github_runner)
                continue

            # reactive runners.
            # If there is no cloud runner, we do not remove  the GitHub runner,
            # as it can be a reactive runner being in the creation phase. The risk
            # is that some offline runners could be left for a while in GitHub.
            if github_runner.instance_id not in cloud_instances_map:
                continue
            cloud_runner = cloud_instances_map[github_runner.instance_id]
            if cloud_runner.cloud_state == CloudRunnerState.CREATED or (
                cloud_runner.cloud_state == CloudRunnerState.ACTIVE
                and cloud_runner.health == HealthState.HEALTHY
            ):
                continue
            github_runners_to_delete.append(github_runner)
        logger.info(
            "Offline github runners to delete: %s:",
            [runner.instance_id for runner in github_runners_to_delete],
        )
        self._platform.delete_runners(github_runners_to_delete)

    @staticmethod
    def _spawn_runners(
        create_runner_args_sequence: Sequence["RunnerManager._CreateRunnerArgs"],
    ) -> tuple[InstanceID, ...]:
        """Spawn runners in parallel using multiprocessing.

        Multiprocessing is only used if there are more than one runner to spawn. Otherwise,
        the runner is created in the current process, which is required for reactive,
        where we don't assume to spawn another process inside the reactive process.

        The length of the create_runner_args is number _create_runner invocation, and therefore the
        number of runner spawned.

        Args:
            create_runner_args_sequence: Sequence of args for invoking _create_runner method.

        Returns:
            A tuple of instance ID's of runners spawned.
        """
        num = len(create_runner_args_sequence)

        if num == 1:
            try:
                return (RunnerManager._create_runner(create_runner_args_sequence[0]),)
            except (RunnerError, PlatformApiError):
                logger.exception("Failed to spawn a runner.")
                return tuple()

        return RunnerManager._spawn_runners_using_multiprocessing(create_runner_args_sequence, num)

    @staticmethod
    def _spawn_runners_using_multiprocessing(
        create_runner_args_sequence: Sequence["RunnerManager._CreateRunnerArgs"], num: int
    ) -> tuple[InstanceID, ...]:
        """Parallel spawn of runners.

        The length of the create_runner_args is number _create_runner invocation, and therefore the
        number of runner spawned.

        Args:
            create_runner_args_sequence: Sequence of args for invoking _create_runner method.
            num: The number of runners to spawn.

        Returns:
            A tuple of instance ID's of runners spawned.
        """
        instance_id_list = []
        with Pool(processes=min(num, 20)) as pool:
            jobs = pool.imap_unordered(
                func=RunnerManager._create_runner, iterable=create_runner_args_sequence
            )
            for _ in range(num):
                try:
                    instance_id = next(jobs)
                except (RunnerError, PlatformApiError):
                    logger.exception("Failed to spawn a runner.")
                except StopIteration:
                    break
                else:
                    instance_id_list.append(instance_id)
        return tuple(instance_id_list)

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
            job_metrics = None

            # We need a guard because pre-job metrics may not be available for idle runners
            # that are deleted.
            if extracted_metrics.pre_job:
                try:
                    job_metrics = github_metrics.job(
                        platform_provider=self._platform,
                        pre_job_metrics=extracted_metrics.pre_job,
                        metadata=extracted_metrics.metadata,
                        runner=extracted_metrics.instance_id,
                    )
                except GithubMetricsError:
                    logger.exception(
                        "Failed to calculate job metrics for %s",
                        extracted_metrics.instance_id,
                    )
            else:
                logger.debug(
                    "No pre-job metrics found for %s, will not calculate job metrics.",
                    extracted_metrics.instance_id,
                )
            issued_events = runner_metrics.issue_events(
                runner_metrics=extracted_metrics,
                job_metrics=job_metrics,
                flavor=self.manager_name,
            )

            for event_type in issued_events:
                total_stats[event_type] = total_stats.get(event_type, 0) + 1

        return total_stats

    @dataclass
    class _CreateRunnerArgs:
        """Arguments for the _create_runner function.

        These arguments are used in the forked processes and should be reviewed.

        Attrs:
            cloud_runner_manager: For managing the cloud instance of the runner.
            platform_provider: To manage self-hosted runner on the Platform side.
            metadata: Metadata for the runner to create.
            labels: List of labels to add to the runners.
            reactive: If the runner is reactive.
        """

        cloud_runner_manager: CloudRunnerManager
        platform_provider: PlatformProvider
        metadata: RunnerMetadata
        labels: list[str]
        reactive: bool

    @staticmethod
    def _create_runner(args: _CreateRunnerArgs) -> InstanceID:
        """Create a single runner.

        This is a staticmethod for usage with multiprocess.Pool.

        Args:
            args: The arguments.

        Returns:
            The instance ID of the runner created.

        Raises:
            RunnerError: On error creating OpenStack runner.
        """
        instance_id = InstanceID.build(args.cloud_runner_manager.name_prefix, args.reactive)
        runner_context, github_runner = args.platform_provider.get_runner_context(
            instance_id=instance_id, metadata=args.metadata, labels=args.labels
        )

        # Update the runner id if necessary
        if not args.metadata.runner_id:
            args.metadata.runner_id = str(github_runner.id)

        try:
            cloud_instance = args.cloud_runner_manager.create_runner(
                instance_id=instance_id,
                metadata=args.metadata,
                runner_context=runner_context,
            )

            # This wait should be deleted to make the runner creation as
            # quick as possible. The waiting should only be done in the
            # reactive case, before checking that a job was taken.
            RunnerManager.wait_for_runner_online(
                platform_provider=args.platform_provider,
                instance_id=cloud_instance.instance_id,
                metadata=cloud_instance.metadata,
            )

        except RunnerError:
            logger.warning("Deleting runner %s from platform after creation failed", instance_id)
            args.platform_provider.delete_runners([github_runner])
            raise
        return instance_id

    @staticmethod
    def wait_for_runner_online(
        platform_provider: PlatformProvider,
        instance_id: InstanceID,
        metadata: RunnerMetadata,
    ) -> None:
        """Wait until the runner is online.

        The constant RUNNER_CREATION_WAITING_TIMES defines the time before calling
        the platform provider to check if the runner is online. Besides online runner,
        deletable runner will also be equivalent to online, as no more waiting should
        be needed.

        Args:
            platform_provider: Platform provider to use for health checks.
            instance_id: InstanceID for the runner to wait for.
            metadata: Metadata for the runner to wait for.

        Raises:
            RunnerError: If the runner did not come online after the specified time.

        """
        for wait_time in RUNNER_CREATION_WAITING_TIMES:
            time.sleep(wait_time)
            try:
                runner_health = platform_provider.get_runner_health(
                    metadata=metadata, instance_id=instance_id
                )
            except PlatformApiError as exc:
                logger.error("Error getting the runner health: %s", exc)
                continue
            if runner_health.online or runner_health.deletable:
                break
        else:
            raise RunnerError(f"Runner {instance_id} did not get online")
