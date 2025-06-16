# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing the GitHub self-hosted runners hosted on cloud instances."""

import copy
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from multiprocessing import Pool
from typing import Iterable, Iterator, Sequence, Type, cast

from github_runner_manager import constants
from github_runner_manager.errors import GithubMetricsError, RunnerError
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    HealthState,
)
from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics import github as github_metrics
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.openstack_cloud.constants import CREATE_SERVER_TIMEOUT
from github_runner_manager.platform.platform_provider import (
    DeleteRunnerBusyError,
    PlatformApiError,
    PlatformProvider,
    PlatformRunnerHealth,
    PlatformRunnerState,
)

logger = logging.getLogger(__name__)

# After a runner is created, there will be as many health checks as
# elements in this variable. The elements in the tuple represent
# the time waiting before each health check against the platform provider.
RUNNER_CREATION_WAITING_TIMES = (60, 60, 120, 240, 480)

# For the reconcile loop, specially for reactive runner (as it is outside of this loop),
# we do not want to delete runners that are offline and not busy in the platform and
# that are not very old in the cloud, as they could be just starting. The creation time will
# be equal to all the possible wait times in creation plus an extra amount.
RUNNER_MAXIMUM_CREATION_TIME = CREATE_SERVER_TIMEOUT + sum(RUNNER_CREATION_WAITING_TIMES) + 120

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
        platform_state: State on the platform.
        cloud_state: State on cloud.
    """

    name: str
    instance_id: InstanceID
    metadata: RunnerMetadata
    health: HealthState
    platform_state: PlatformRunnerState | None
    cloud_state: CloudRunnerState

    def __init__(
        self,
        cloud_instance: CloudRunnerInstance,
        platform_health_state: PlatformRunnerHealth | None,
    ):
        """Construct an instance.

        Args:
            cloud_instance: Information on the cloud instance.
            platform_health_state: Health state in the platform provider.
        """
        self.name = cloud_instance.name
        self.instance_id = cloud_instance.instance_id
        self.metadata = cloud_instance.metadata
        self.health = cloud_instance.health
        self.platform_state = (
            PlatformRunnerState.from_platform_health(platform_health_state)
            if platform_health_state is not None
            else None
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

    def get_runners(self) -> tuple[RunnerInstance, ...]:
        """Get runners with health information.

        Returns:
            Information on the runners.
        """
        logger.debug("runner_manager::get_runners")
        runner_instances = []
        cloud_runners = self._cloud.get_runners()
        runners_health_response = self._platform.get_runners_health(cloud_runners)
        logger.info("clouds runners response %s", cloud_runners)
        logger.info("runner health response %s", runners_health_response)
        runners_health = runners_health_response.requested_runners
        health_runners_map = {runner.identity.instance_id: runner for runner in runners_health}
        for cloud_runner in cloud_runners:
            if cloud_runner.instance_id not in health_runners_map:
                runner_instance = RunnerInstance(cloud_runner, None)
                runner_instance.health = HealthState.UNKNOWN
                runner_instances.append(runner_instance)
                continue
            health_runner = health_runners_map[cloud_runner.instance_id]
            if health_runner.deletable:
                cloud_runner.health = HealthState.UNHEALTHY
            elif health_runner.online:
                cloud_runner.health = HealthState.HEALTHY
            else:
                cloud_runner.health = HealthState.UNHEALTHY
            runner_instance = RunnerInstance(cloud_runner, health_runner)
            runner_instances.append(runner_instance)
        return cast(tuple[RunnerInstance], tuple(runner_instances))

    def delete_runners(self, num: int) -> IssuedMetricEventsStats:
        """Delete runners.

        Args:
            num: The number of runner to delete.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        logger.info("runner_manager::delete_runners Deleting %s runners", num)
        extracted_runner_metrics = self._cleanup_resources(
            force_delete=True, maximum_runners_to_delete=num
        )
        return self._issue_runner_metrics(metrics=iter(extracted_runner_metrics))

    def flush_runners(
        self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE
    ) -> IssuedMetricEventsStats:
        """Delete runners according to state.

        Args:
            flush_mode: The type of runners affect by the deletion.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        logger.info("runner_manager::flush_runners. mode %s", flush_mode)
        match flush_mode:
            case FlushMode.FLUSH_IDLE:
                logger.info("Flushing idle runners...")
            case FlushMode.FLUSH_BUSY:
                logger.info("Flushing idle and busy runners...")
            case _:
                logger.critical(
                    "Unknown flush mode %s encountered, contact developers", flush_mode
                )

        flush_busy = False
        if flush_mode == FlushMode.FLUSH_BUSY:
            flush_busy = True

        extracted_runner_metrics = self._cleanup_resources(
            clean_idle=True, force_delete=flush_busy
        )
        return self._issue_runner_metrics(metrics=iter(extracted_runner_metrics))

    def cleanup(self) -> IssuedMetricEventsStats:
        """Run cleanup of the runners and other resources.

        Returns:
            Stats on metrics events issued during the cleanup of runners.
        """
        logger.info("runner_manager::cleanup")
        deleted_runner_metrics = self._cleanup_resources()
        return self._issue_runner_metrics(metrics=iter(deleted_runner_metrics))

    def _cleanup_resources(
        self,
        clean_idle: bool = False,
        force_delete: bool = False,
        maximum_runners_to_delete: int | None = None,
    ) -> Iterable[runner_metrics.RunnerMetrics]:
        """Cleanup the indicated runners in the platform and in the cloud."""
        logger.info(
            " _cleanup_resources idle: %s, force: %s",
            clean_idle,
            force_delete,
        )
        cloud_runners = self._cloud.get_runners()
        logger.info("cleanup cloud_runners %s", cloud_runners)
        runners_health_response = self._platform.get_runners_health(cloud_runners)
        logger.info("cleanup health_response %s", runners_health_response)

        # Clean dangling resources in the cloud
        self._cloud.cleanup()

        # Always clean all runners in the platform that are not in the cloud
        self._clean_platform_runners(runners_health_response.non_requested_runners)

        cloud_runners_to_delete = list(cloud_runners)
        health_runners_map = {
            health.identity.instance_id: health
            for health in runners_health_response.requested_runners
        }

        cloud_runners_to_delete = list(
            filter(
                lambda cloud_runner: _filter_runner_to_delete(
                    cloud_runner,
                    health_runners_map.get(cloud_runner.instance_id),
                    clean_idle=clean_idle,
                    force_delete=force_delete,
                ),
                cloud_runners_to_delete,
            )
        )

        if maximum_runners_to_delete:
            cloud_runners_to_delete.sort(
                key=partial(_runner_deletion_sort_key, health_runners_map)
            )
            cloud_runners_to_delete = cloud_runners_to_delete[:maximum_runners_to_delete]

        return self._delete_cloud_runners(
            cloud_runners_to_delete,
            runners_health_response.requested_runners,
            delete_busy_runners=force_delete,
        )

    def _delete_cloud_runners(
        self,
        cloud_runners: Sequence[CloudRunnerInstance],
        runners_health: Sequence[PlatformRunnerHealth],
        delete_busy_runners: bool = False,
    ) -> Iterable[runner_metrics.RunnerMetrics]:
        """Delete runners in the platform ant the cloud.

        If delete_busy_runners is False, when the platform provider fails in deleting the
        runner because it can be busy, will mean that that runner should not be deleted.
        """
        extracted_runner_metrics = []
        health_runners_map = {health.identity.instance_id: health for health in runners_health}
        for cloud_runner in cloud_runners:
            logging.info("Trying to delete cloud_runner %s", cloud_runner)
            runner_health = health_runners_map.get(cloud_runner.instance_id)
            if runner_health and runner_health.runner_in_platform:
                try:
                    self._platform.delete_runner(runner_health.identity)
                except DeleteRunnerBusyError:
                    if not delete_busy_runners:
                        logger.warning(
                            "Skipping deletion as the runner is busy. %s", cloud_runner.instance_id
                        )
                        continue
                    logger.info("Deleting busy runner: %s", cloud_runner.instance_id)
                except PlatformApiError as exc:
                    if not delete_busy_runners:
                        logger.warning(
                            "Failed to delete platform runner %s. %s. Skipping.",
                            cloud_runner.instance_id,
                            exc,
                        )
                        continue
                    logger.warning(
                        "Deleting runner: %s after platform failure %s.",
                        cloud_runner.instance_id,
                        exc,
                    )

            logging.info("Delete runner in cloud: %s", cloud_runner.instance_id)
            runner_metric = self._cloud.delete_runner(cloud_runner.instance_id)
            if not runner_metric:
                logger.error("No metrics returned after deleting %s", cloud_runner.instance_id)
            else:
                extracted_runner_metrics.append(runner_metric)
        return extracted_runner_metrics

    def _clean_platform_runners(self, runners: list[RunnerIdentity]) -> None:
        """Clean the specified runners in the platform."""
        for runner in runners:
            try:
                self._platform.delete_runner(runner)
            except DeleteRunnerBusyError:
                logger.warning("Tried to delete busy runner in cleanup %s", runner)
            except PlatformApiError:
                logger.warning("Failed to delete platform runner %s", runner)

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
        with Pool(processes=min(num, 30)) as pool:
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

        runner_identity = RunnerIdentity(instance_id=instance_id, metadata=args.metadata)
        try:
            args.cloud_runner_manager.create_runner(
                runner_identity=runner_identity,
                runner_context=runner_context,
            )
        except RunnerError:
            logger.warning("Deleting runner %s from platform after creation failed", instance_id)
            args.platform_provider.delete_runner(github_runner.identity)
            raise
        return instance_id

    @staticmethod
    def wait_for_runner_online(
        platform_provider: PlatformProvider,
        runner_identity: RunnerIdentity,
    ) -> None:
        """Wait until the runner is online.

        The constant RUNNER_CREATION_WAITING_TIMES defines the time before calling
        the platform provider to check if the runner is online. Besides online runner,
        deletable runner will also be equivalent to online, as no more waiting should
        be needed.

        Args:
            platform_provider: Platform provider to use for health checks.
            runner_identity: Identity of the runner.

        Raises:
            RunnerError: If the runner did not come online after the specified time.

        """
        for wait_time in RUNNER_CREATION_WAITING_TIMES:
            time.sleep(wait_time)
            try:
                runner_health = platform_provider.get_runner_health(runner_identity)
            except PlatformApiError:
                logger.exception("Error getting the runner health: %s", runner_identity)
                continue
            if runner_health.online or runner_health.deletable:
                logger.info("Runner %s online", runner_identity)
                break
            logger.info("Runner %s not yet online", runner_identity)
        else:
            raise RunnerError(f"Runner {runner_identity} did not get online")


def _filter_runner_to_delete(
    cloud_runner: CloudRunnerInstance,
    health: PlatformRunnerHealth | None,
    *,
    clean_idle: bool = False,
    force_delete: bool = False,
) -> bool:
    """Filter runners to delete based on the input arguments.

    This is the main function to filter what runners to delete. Runners that are deletable
    in the health information from platform should be deleted. For the other cases, the
    filtering will depend on the input arguments.

    Args:
        cloud_runner: Cloud runner.
        health: Platform runner or None if health information is not available.
        clean_idle: Remove runners that are idle.
        force_delete: Delete the runner in all conditions.

    Returns:
        True if the runner should be deleted
    """
    if force_delete:
        return True

    # Do not delete runners without health information.
    if health is None:
        logger.info("No health information for %s. Skip deletion.", cloud_runner.instance_id)
        return False

    # Always delete deletable runners with health information.
    if health.deletable:
        return True

    if clean_idle and health.online and not health.busy:
        return True

    if not health.online and not health.busy:
        # Kill old runners that are offline and idle as they could be in failed state.
        # We may also kill here runners that were online and not busy and went temporarily to
        # offline, but that should not be an issue, as those runners will be spawned again.
        if cloud_runner.is_older_than(RUNNER_MAXIMUM_CREATION_TIME):
            return True

    return False


def _runner_deletion_sort_key(
    health_runners_map: dict[InstanceID, PlatformRunnerHealth], cloud_runner: CloudRunnerInstance
) -> int:
    """Order the runners in accordance to how inconvenient it is to delete them.

    Deletable runner should be the first to be removed, and busy runner should be the last
    ones to delete. For the other ones it is a bit more arbitrary, but runners without health
    information should not be preferred to be deleted, as they could be busy.
    The value returned will be used for the sorting function, so runners with
    smaller values will be deleted first.
    """
    if cloud_runner.instance_id in health_runners_map:
        health = health_runners_map[cloud_runner.instance_id]
        if health.deletable:
            return 1
        if health.busy:
            return 4
        return 2
    return 3
