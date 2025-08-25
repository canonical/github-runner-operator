# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing the GitHub self-hosted runners hosted on cloud instances."""

import copy
import logging
from dataclasses import dataclass
from enum import Enum, auto
from multiprocessing import Pool
from typing import Iterator, Sequence, Type

from github_runner_manager import constants
from github_runner_manager.errors import GithubMetricsError, RunnerError
from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.manager.vm_manager import VM, CloudRunnerManager, HealthState, VMState
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics import github as github_metrics
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.openstack_cloud.constants import CREATE_SERVER_TIMEOUT
from github_runner_manager.platform.platform_provider import (
    PlatformApiError,
    PlatformProvider,
    PlatformRunnerHealth,
    PlatformRunnerState,
    RunnersHealthResponse,
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


@dataclass(frozen=True)
class RunnerInstance:
    """Represents an instance of runner.

    Attributes:
        name: Full name of the runner. Managed by the cloud runner manager.
        instance_id: ID of the runner. Managed by the runner manager.
        metadata: Metadata for the runner.
        health: The health state of the runner.
        platform_state: State on the platform.
        platform_health: Health information queried from the platform provider.
        cloud_state: State on cloud.
    """

    name: str
    instance_id: InstanceID
    metadata: RunnerMetadata
    platform_state: PlatformRunnerState | None
    platform_health: PlatformRunnerHealth | None
    cloud_state: VMState

    @property
    def health(self) -> HealthState:
        """Overall health state of the runner instance."""
        if not self.platform_health:
            return HealthState.UNKNOWN
        if self.platform_health.deletable:
            return HealthState.UNHEALTHY
        if self.platform_health.online:
            return HealthState.HEALTHY
        return HealthState.UNKNOWN

    @classmethod
    def from_cloud_and_platform_health(
        cls,
        cloud_instance: VM,
        platform_health_state: PlatformRunnerHealth | None,
    ) -> "RunnerInstance":
        """Construct an instance.

        Args:
            cloud_instance: Information on the cloud instance.
            platform_health_state: Health state in the platform provider.

        Returns:
            The RunnerInstance instantiated from cloud instance and platform state.
        """
        return cls(
            name=cloud_instance.instance_id.name,
            instance_id=cloud_instance.instance_id,
            metadata=cloud_instance.metadata,
            platform_state=(
                PlatformRunnerState.from_platform_health(health=platform_health_state)
                if platform_health_state is not None
                else None
            ),
            platform_health=platform_health_state,
            cloud_state=cloud_instance.state,
        )


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
        vms = self._cloud.get_vms()
        logger.info("list vms response: %s", vms)
        runners_health_response = self._platform.get_runners_health(vms)
        logger.info("runner health response %s", runners_health_response)
        runners_health = runners_health_response.requested_runners
        health_runners_map = {runner.identity.instance_id: runner for runner in runners_health}
        return tuple(
            RunnerInstance.from_cloud_and_platform_health(
                cloud_instance=vm,
                platform_health_state=health_runners_map.get(vm.instance_id, None),
            )
            for vm in vms
        )

    def delete_runners(self, num: int) -> IssuedMetricEventsStats:
        """Delete runners.

        Args:
            num: The number of runner to delete.

        Returns:
            Stats on metrics events issued during the deletion of runners.
        """
        logger.info("runner_manager::delete_runners Deleting %s runners", num)
        vms = self._cloud.get_vms()
        logger.info("VMs: %s", vms)
        runners_health_response = self._platform.get_runners_health(requested_runners=vms)
        logger.info("Runner health: %s", runners_health_response)

        platform_runner_ids_to_cleanup = _get_platform_runners_to_cleanup(
            runners=runners_health_response, vms=vms
        )
        logger.info("Runners to clean up: %s", platform_runner_ids_to_cleanup)
        num_runners_to_cleanup = len(platform_runner_ids_to_cleanup)
        if len(platform_runner_ids_to_cleanup) < num:
            num -= num_runners_to_cleanup

        runners_not_marked_for_cleanup = [
            runner
            for runner in runners_health_response.requested_runners
            if runner.identity.metadata.runner_id
            and runner.identity.metadata.runner_id not in platform_runner_ids_to_cleanup
        ]
        platform_runner_ids_to_scaledown = _get_platform_runners_to_scale_down(
            runners=runners_not_marked_for_cleanup,
            num=num,
        )
        logger.info("Runners to scale down: %s", platform_runner_ids_to_scaledown)
        platform_runner_ids_to_delete = list(
            platform_runner_ids_to_cleanup | platform_runner_ids_to_scaledown
        )
        logger.info("Deleting platform runners: %s", platform_runner_ids_to_delete)
        deleted_runner_ids = self._platform.delete_runners(
            runner_ids=platform_runner_ids_to_delete
        )
        logger.info("Deleted runners: %s", deleted_runner_ids)

        vm_ids_to_cleanup = _get_vms_to_cleanup(
            vms=vms,
            cleanedup_runner_ids=platform_runner_ids_to_delete,
            runners=runners_health_response,
        )
        logger.info("Extracting metrics from VMs: %s", vm_ids_to_cleanup)
        extracted_metrics = self._cloud.extract_metrics(instance_ids=list(vm_ids_to_cleanup))
        logger.info("Deleting VMs: %s", vm_ids_to_cleanup)
        self._cloud.delete_vms(instance_ids=list(vm_ids_to_cleanup))

        return self._issue_runner_metrics(metrics=iter(extracted_metrics))

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
        vms = self._cloud.get_vms()
        logger.info("VMs: %s", vms)
        runners_health_response = self._platform.get_runners_health(requested_runners=vms)
        logger.info("Runner health: %s", runners_health_response)

        platform_runner_ids_to_cleanup = _get_platform_runners_to_cleanup(
            runners=runners_health_response, vms=vms
        )
        logger.info("Runners to clean up: %s", platform_runner_ids_to_cleanup)
        platform_runner_ids_to_flush = _get_platform_runners_to_flush(
            runners=runners_health_response, flush_mode=flush_mode
        )
        logger.info("Runners to flush: %s", platform_runner_ids_to_flush)
        platform_runner_ids_to_delete = list(
            platform_runner_ids_to_cleanup | platform_runner_ids_to_flush
        )
        logger.info("Deleting platform runners: %s", platform_runner_ids_to_flush)
        deleted_runner_ids = self._platform.delete_runners(
            runner_ids=platform_runner_ids_to_delete
        )
        logger.info("Deleted runners: %s", deleted_runner_ids)

        vm_ids_to_cleanup = _get_vms_to_cleanup(
            vms=vms,
            cleanedup_runner_ids=platform_runner_ids_to_delete,
            runners=runners_health_response,
        )
        logger.info("Extracting metrics from VMs: %s", vm_ids_to_cleanup)
        extracted_metrics = self._cloud.extract_metrics(instance_ids=list(vm_ids_to_cleanup))
        logger.info("Deleting VMs: %s", vm_ids_to_cleanup)
        self._cloud.delete_vms(instance_ids=list(vm_ids_to_cleanup))

        return self._issue_runner_metrics(metrics=iter(extracted_metrics))

    def cleanup(self) -> IssuedMetricEventsStats:
        """Run cleanup of the runners and other resources.

        Returns:
            Stats on metrics events issued during the cleanup of runners.
        """
        logger.info("runner_manager::cleanup")
        vms = self._cloud.get_vms()
        logger.info("VMs: %s", vms)
        runners_health_response = self._platform.get_runners_health(requested_runners=vms)
        logger.info("Runner health: %s", runners_health_response)

        self._cloud.cleanup()
        platform_runner_ids_to_cleanup = _get_platform_runners_to_cleanup(
            runners=runners_health_response, vms=vms
        )
        logger.info("Cleaning up platform runners: %s", platform_runner_ids_to_cleanup)
        cleanedup_runner_ids = self._platform.delete_runners(
            runner_ids=list(platform_runner_ids_to_cleanup)
        )
        logger.info("Cleaned up platform runners: %s", cleanedup_runner_ids)

        vm_ids_to_cleanup = _get_vms_to_cleanup(
            vms=vms,
            cleanedup_runner_ids=list(platform_runner_ids_to_cleanup),
            runners=runners_health_response,
        )
        logger.info("Extracting metrics from VMs: %s", vm_ids_to_cleanup)
        extracted_metrics = self._cloud.extract_metrics(instance_ids=list(vm_ids_to_cleanup))
        logger.info("Cleaning up VMs: %s", vm_ids_to_cleanup)
        self._cloud.delete_vms(instance_ids=list(vm_ids_to_cleanup))

        return self._issue_runner_metrics(metrics=iter(extracted_metrics))

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
        runner_context, runner_info = args.platform_provider.get_runner_context(
            instance_id=instance_id, metadata=args.metadata, labels=args.labels
        )

        # Update the runner id if necessary
        if not args.metadata.runner_id:
            args.metadata.runner_id = str(runner_info.id)

        runner_identity = RunnerIdentity(instance_id=instance_id, metadata=args.metadata)
        try:
            args.cloud_runner_manager.create_runner(
                runner_identity=runner_identity,
                runner_context=runner_context,
            )
        except RunnerError:
            logger.warning("Deleting runner %s from platform after creation failed", instance_id)
            args.platform_provider.delete_runners(runner_ids=[args.metadata.runner_id])
            raise
        return instance_id


def _get_platform_runners_to_cleanup(
    *, runners: RunnersHealthResponse, vms: Sequence[VM]
) -> set[str]:
    """Determine platform runners to clean up.

    1. Always clean up danging platform runners (platform runners that have no VM associated).
    2. Always clean up deletable platform runners (deletable decision made by platform provider).
    3. Clean up runners that in offline-idle status that have timed out where the possible
        scenarios is:
        - runner registered (during registration token generation) but VM has failed to spawn.

    Args:
        runners: platform runners health information.
        vms: cloud VM state.

    Returns:
        The runner IDs to delete.
    """
    # Always clean all runners in the platform that are not in the cloud
    dangling_runners: set[str] = set(
        runner.metadata.runner_id
        for runner in runners.non_requested_runners
        if runner.metadata.runner_id
    )
    logger.debug("Dangling runners IDs: %s", dangling_runners)

    deletable_runners: set[str] = set(
        runner.identity.metadata.runner_id
        for runner in runners.requested_runners
        if runner.deletable and runner.identity.metadata.runner_id
    )
    logger.debug("Deletable runner IDs: %s", deletable_runners)

    vm_instance_id_map = {vm.instance_id: vm for vm in vms}
    # Kill old runners that are offline and idle as they could be in failed state.
    # We may also kill here runners that were online and not busy and went temporarily to
    # offline, but that should not be an issue, as those runners will be spawned again.
    timed_out_offline_idle_runners: set[str] = set(
        runner.identity.metadata.runner_id
        for runner in runners.requested_runners
        if runner.identity.metadata.runner_id
        and not runner.online
        and not runner.busy
        and runner.identity.instance_id in vm_instance_id_map
        and vm_instance_id_map[runner.identity.instance_id].is_older_than(
            RUNNER_MAXIMUM_CREATION_TIME
        )
    )
    logger.debug("Timed out offline idle runner IDs: %s", timed_out_offline_idle_runners)

    return dangling_runners | deletable_runners | timed_out_offline_idle_runners


def _get_platform_runners_to_flush(
    runners: RunnersHealthResponse, flush_mode: FlushMode
) -> set[str]:
    """Determine runners to flush.

    Args:
        runners: RunnersHealthResponse
        flush_mode: Runner flushing strategy.
    """
    online_idle_runners = set(
        runner.identity.metadata.runner_id
        for runner in runners.requested_runners
        if runner.identity.metadata.runner_id and runner.online and not runner.busy
    )
    logger.debug("Online idle runners: %s", online_idle_runners)
    busy_runners = set(
        runner.identity.metadata.runner_id
        for runner in runners.requested_runners
        if runner.identity.metadata.runner_id
        and runner.identity.metadata.runner_id not in online_idle_runners
    )
    logger.debug("Busy runners: %s", busy_runners)
    match flush_mode:
        case FlushMode.FLUSH_IDLE:
            return online_idle_runners
        case FlushMode.FLUSH_BUSY:
            return online_idle_runners | busy_runners
        case _:
            logger.critical("Unknown flush mode %s encountered, contact developers", flush_mode)
            return set()


def _get_platform_runners_to_scale_down(
    runners: Sequence[PlatformRunnerHealth], num: int
) -> set[str]:
    """Determine the number of runners to scale down.

    Args:
        runners: pool of runners to select to scale down.
        num: number of runners to scale down by.
    """
    # prioritize deletable --> idle --> busy
    sorted_runners = sorted(
        runners, key=lambda runner: 1 if runner.deletable else 2 if not runner.busy else 3
    )
    return set(
        runner.identity.metadata.runner_id
        for runner in sorted_runners[:num]
        if runner.identity.metadata.runner_id
    )


def _get_vms_to_cleanup(
    *, vms: Sequence[VM], cleanedup_runner_ids: list[str], runners: RunnersHealthResponse
) -> set[InstanceID]:
    """Determine cloud VMs to clean up.

    Args:
        vms: cloud VM state.
        cleanedup_runner_ids: platform runners that have been cleaned up.
        runners: platform runners health information.

    Returns:
        The VM InstanceIDs (NOT VM UUIDs) to clean up.
    """
    vms_without_runner_ids = set(vm.instance_id for vm in vms if not vm.metadata.runner_id)
    logger.info("VMs without platform runner ID metadata:\n%s", vms_without_runner_ids)
    vms_with_deleted_runners = set(
        vm.instance_id
        for vm in vms
        if vm.metadata.runner_id and vm.metadata.runner_id in cleanedup_runner_ids
    )
    logger.info("VMs with deleted platform runners:\n%s", vms_with_deleted_runners)

    return vms_without_runner_ids | vms_with_deleted_runners


def _runner_deletion_sort_key(
    health_runners_map: dict[InstanceID, PlatformRunnerHealth], cloud_runner: VM
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
