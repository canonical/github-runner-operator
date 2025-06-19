#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""A module for managing resources via reconcile loop."""
import logging
import multiprocessing
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Iterable, Protocol, Sequence, Type, cast
from urllib.parse import urlparse

from kombu import Message
from kombu.simple import SimpleQueue
from pydantic import BaseModel, HttpUrl, ValidationError, validator

from github_runner_manager.errors import RunnerError
from github_runner_manager.manager.cloud_runner_manager import CloudRunnerInstance, InstanceID
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    Platform,
    PlatformApiError,
    PlatformRunner,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
    SelfHostedRunner,
)

logger = logging.getLogger(__name__)

# This control message is for testing. The reactive process will stop consuming messages
# when the message is sent. This message does not come from the router.
END_PROCESSING_PAYLOAD = "__END__"


class ReconcileAlgorithm(str, Enum):
    """Which algorithm to use for reconciliation.

    Attributes:
        REACTIVE: Reactive algorithm, listening to upstream request queue.
        PRESPAWN: Prespawn algorithm, generates runner creation request based on current state.
    """

    REACTIVE = "REACTIVE"
    PRESPAWN = "PRESPAWN"


@dataclass
class ReconcileConfigBase:
    """Base class for reconcile algorithm.

    Attributes:
        algorithm: Which algorithm to use for reconciliation.
        base_quantity: Number of prespawned application to be maintained.
    """

    algorithm: ReconcileAlgorithm
    base_quantity: int
    vm_image: str
    vm_flavor: str


@dataclass
class PrespawnConfig(ReconcileConfigBase):
    """Configurations for the reconcile algorithm.

    Attributes:
        algorithm: Prespawn reconciliation algorithm.
    """

    algorithm = ReconcileAlgorithm.PRESPAWN


@dataclass
class ReactiveConfig(ReconcileConfigBase):
    """Configurations for the reactive algorithm.

    Attributes:
        algorithm: Reactive reconciliation algorithm.
    """

    algorithm = ReconcileAlgorithm.REACTIVE
    queue: SimpleQueue
    supported_labels: set[str]


class _ReconciliationAction(str, Enum):
    """Reconciliation action options.

    Attributes:
        CREATE: Request creation of new runners.
        DOWNSCALE: Request downscaling of current runners.
        NOOP: Do nothing.
    """

    CREATE = "CREATE"
    DOWNSCALE = "DOWNSCALE"
    NOOP = "NOOP"


@dataclass
class _ReconcileActionPlanBase:
    """Actions computed after reconciling current state.

    Attributes:
        algorithm: Which algorithm to use for reconciliation.
    """

    algorithm: ReconcileAlgorithm
    action: _ReconciliationAction


@dataclass
class _PreaspawnReconcileActionPlan(_ReconcileActionPlanBase):
    """Action plan generated after reconciling current state for Prespawn runners.

    Attributes:
        quantity: Number of reactive runners to spawn.
    """

    quantity: int


@dataclass
class _ReactiveReconcileActionPlan(_ReconcileActionPlanBase):
    """Action plan generated after reconciling current state for Reactive runners.

    Attributes:
        spawn_runner_configs: List of runner configurations to spawn runners with.
    """

    spawn_runner_configs: list["_SpawnRunnerConfig"]


@dataclass
class ReconcileManagerConfig:
    """Configuration for reconcile manager.

    Attributes:
        manager_name: The unique name of the reconcile manager, use to identify resources.
        labels: The labels to attach to the runners created by this manager, for the users to\
            target the desired runner for their jobs.
        python_path: The PYTHONPATH to access the github-runner-manager library.
    """

    manager_name: str
    labels: list[str]
    python_path: str | None


class SupportsPlatformProvider(Protocol):
    """Any service that supports interacting with CI runner provider."""

    platform: Platform

    def list_runners(self) -> list[PlatformRunner]:
        """List runners owned by the application in the platform."""
        ...

    def get_runner(self, runner_identity: RunnerIdentity) -> PlatformRunner | None:
        """Get a single runner from the platform if it exists."""
        ...

    def delete_runners(self, runners: list[PlatformRunner]) -> list[PlatformRunner]:
        """Request deletion of runners on the platform."""
        ...

    def delete_runner(self, runner_identity: RunnerIdentity) -> RunnerIdentity | None:
        """Delete a single runner from the platform if it exists."""
        ...

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get a context for creating a new runner on the platform.

        We shoud look into this method and abstract it with information necessary, and name it
        something meaningful to the business logic, rather than context.
        """
        ...

    def get_job(
        self,
    ) -> JobInfo | None:
        """Get the job from the platform.

        Args:
            runner_identity: The identity of the runner to get the job for.
        """
        ...


class SupportsCloudProvider(Protocol):
    """Any service that supports interacting with cloud VM provider."""

    @property
    def name_prefix(self) -> str:
        """Prefix for resource names.

        We should probably have an "InstanceBuilder" class that abstracts shared information
        about the instance that can generate the name with minimum information from the caller
        class. Leave it as is to reduce the scope of refactoring.
        """
        ...

    def create_vm(
        self, *, runner_identity: RunnerIdentity, vm_config: OpenStackServerConfig
    ) -> CloudRunnerInstance:
        """Create new VM for a runner."""
        ...

    def list_vms(self) -> list[CloudRunnerInstance]:
        """List VMs owned by the applicadtion in the cloud."""
        ...

    def delete_vms(self, *, vms: Sequence[CloudRunnerInstance]) -> list[CloudRunnerInstance]:
        """Request deletion of VMs."""
        ...


class SupportsRunnerMetrics(Protocol):
    """Any service that supports propagating metrics of a completed runner."""

    def propagate_metrics(self, vms: Sequence[CloudRunnerInstance]) -> None:
        """Propagates metrics from completed runner VM."""
        ...


Labels = set[str]


class JobDetails(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        url: The URL of the job to check its status.
    """

    labels: Labels
    url: HttpUrl

    @validator("url")
    @classmethod
    def check_job_url_path_is_not_empty(cls, v: HttpUrl) -> HttpUrl:
        """Check that the job_url path is not empty.

        Args:
            v: The job_url to check.

        Returns:
            The job_url if it is valid.

        Raises:
            ValueError: If the job_url path is empty.
        """
        if not v.path:
            raise ValueError("path must be provided")
        return v


class Reconciler:
    """A manager using the reconcile loop algorithm."""

    def __init__(
        self,
        platform_provider: SupportsPlatformProvider,
        cloud_provider: SupportsCloudProvider,
        metrics_provider: SupportsRunnerMetrics,
        config: ReconcileManagerConfig,
        algorithm_config: PrespawnConfig | ReactiveConfig,
    ):
        """Initialize the reconciler.

        Args:
            platform_provider: The runner platform service provider.
            cloud_provider: The runner cloud service provider.
            metrics_provider: The idempotent metrics service provider.
            config: Configuration for the reconciler manager.
            algorithm_config: Configuration for the reconcile algorithm.
        """
        self._platform = platform_provider
        self._cloud = cloud_provider
        self._metrics = metrics_provider
        self._config = config
        self._algorithm_config = algorithm_config

    def reconcile(self) -> None:
        """Run a single reconcile iteration."""
        # calculate resources to clean up
        vms = self._cloud.list_vms()
        runners = self._platform.list_runners()
        vms_to_cleanup = self._get_vms_to_cleanup(vms=vms, runners=runners)
        runners_to_cleanup = self._get_runners_to_cleanup(runners=runners, vms=vms)

        # fetch metrics from resources that require cleanup
        self._metrics.propagate_metrics(vms=vms_to_cleanup)

        # clean up resources
        deleted_vms = self._cloud.delete_vms(vms=vms_to_cleanup)
        self._platform.delete_runners(runners=runners_to_cleanup)

        # calculate resources to create
        remaining_vms = set(vms) - set(deleted_vms)
        action_plan: _ReconcileActionPlanBase
        match self._algorithm_config.algorithm:
            case ReconcileAlgorithm.REACTIVE:
                action_plan = self._plan_reactive_runners(vms=remaining_vms)
                self._spawn_reactive_runners(plan=action_plan)
            case ReconcileAlgorithm.PRESPAWN:
                action_plan = self._plan_prespawn_runners(vms=remaining_vms)
                self._spawn_prespawn_runners(plan=action_plan)

    def _get_vms_to_cleanup(
        self, vms: Sequence[CloudRunnerInstance], runners: Sequence[PlatformRunner]
    ) -> list[CloudRunnerInstance]:
        """Get the VMs that need to be cleaned up.

        Cleanup algorithm:
        - VMs that are older than 5 minutes that are not registered in the platform.

        Args:
            vms: The list of VMs to check if they need to be cleaned up.
            runners: The list of runners to check the VMs against.

        Returns:
            The list of VMs that require cleaning up.
        """
        runner_instance_ids = {runner.identity.instance_id for runner in runners}
        return [
            vm
            for vm in vms
            if vm.instance_id not in runner_instance_ids
            and vm.created_at < datetime.now() - timedelta(minutes=5)
        ]

    def _get_runners_to_cleanup(
        self, runners: Sequence[PlatformRunner], vms: Sequence[CloudRunnerInstance]
    ) -> list[PlatformRunner]:
        """Get the runners that need to be cleaned up.

        Cleanup algorithm:
        - Runners in the platform that are not paired to any of the VMs.

        Args:
            runners: The list of runners to check if they need to be cleaned up.
            vms: The list of VMs to check the runners against.

        Returns:
            The list of runners that require cleaning up.
        """
        vm_instance_ids = {vm.instance_id for vm in vms}
        return [runner for runner in runners if runner.identity.instance_id not in vm_instance_ids]

    def _plan_reactive_runners(
        self, vms: Iterable[CloudRunnerInstance]
    ) -> _ReactiveReconcileActionPlan:
        """Create the reactive runners.

        Args:
            vms: The current vms in the cloud.
        """
        reactive_config = cast(ReactiveConfig, self._algorithm_config)
        queue_size = reactive_config.queue.qsize()
        if not queue_size:
            return _ReactiveReconcileActionPlan(
                algorithm=ReconcileAlgorithm.REACTIVE,
                action=_ReconciliationAction.NOOP,
                spawn_runner_configs=[],
            )

        diff = reactive_config.base_quantity - len(tuple(vms))
        num_reactive_to_spawn = min(diff, queue_size)
        if num_reactive_to_spawn == 0:
            return _ReactiveReconcileActionPlan(
                algorithm=ReconcileAlgorithm.REACTIVE,
                action=_ReconciliationAction.NOOP,
                spawn_runner_configs=[],
            )
        elif num_reactive_to_spawn < 0:
            return _ReactiveReconcileActionPlan(
                algorithm=ReconcileAlgorithm.REACTIVE,
                action=_ReconciliationAction.DOWNSCALE,
                spawn_runner_configs=[],
            )

        reactive_job_configs = []
        for _ in range(num_reactive_to_spawn):
            reactive_msg: Message = reactive_config.queue.get(block=True, timeout=30)
            if reactive_msg.payload == END_PROCESSING_PAYLOAD:
                reactive_msg.ack()
                break
            try:
                job = JobDetails.parse_raw(reactive_msg.payload)
            except ValidationError:
                reactive_msg.reject(requeue=False)
                # handle something critical here
                continue
            # check all labels are supported
            if not all(label in reactive_config.supported_labels for label in job.labels):
                reactive_msg.reject(requeue=False)
                # handle something critical here
                continue
            # build metadata
            instance_id = InstanceID.build(
                self._cloud.name_prefix,
                reactive=False,
            )
            runner_metadata = _build_runner_metadata(job_url=job.url)
            runner_context, runner = self._platform.get_runner_context(
                instance_id=instance_id, metadata=runner_metadata, labels=self._config.labels
            )
            reactive_job_configs.append(
                _SpawnRunnerConfig(
                    platform_provider=self._platform,
                    cloud_provider=self._cloud,
                    instance_id=instance_id,
                    algorithm=ReconcileAlgorithm.REACTIVE,
                    vm_config=OpenStackServerConfig(
                        image=reactive_config.vm_image,
                        flavor=reactive_config.vm_flavor,
                    ),
                    runner=runner,
                    runner_context=runner_context,
                    runner_metadata=runner_metadata,
                )
            )
        return _ReactiveReconcileActionPlan(
            algorithm=ReconcileAlgorithm.REACTIVE,
            action=_ReconciliationAction.CREATE,
            spawn_runner_configs=reactive_job_configs,
        )

    def _plan_prespawn_runners(
        self, vms: Iterable[CloudRunnerInstance]
    ) -> _PreaspawnReconcileActionPlan:
        """Create prespawned runners.

        Args:
            vms: The current vms in the cloud.

        Returns:
            The reconcile action plan.
        """
        prespawn_config = cast(PrespawnConfig, self._algorithm_config)
        diff = prespawn_config.base_quantity - len(tuple(vms))
        if diff == 0:
            return _PreaspawnReconcileActionPlan(
                algorithm=ReconcileAlgorithm.PRESPAWN,
                action=_ReconciliationAction.NOOP,
                quantity=0,
            )
        elif diff > 0:
            return _PreaspawnReconcileActionPlan(
                algorithm=ReconcileAlgorithm.PRESPAWN,
                action=_ReconciliationAction.CREATE,
                quantity=diff,
            )
        return _PreaspawnReconcileActionPlan(
            algorithm=ReconcileAlgorithm.PRESPAWN,
            action=_ReconciliationAction.DOWNSCALE,
            quantity=-diff,
        )

    def _spawn_reactive_runners(
        self, plan: _ReactiveReconcileActionPlan
    ) -> tuple[InstanceID, ...]:
        """Spawn runners in a reactive manner."""
        instance_id_list = []
        with multiprocessing.Pool(processes=min(len(plan.spawn_runner_configs), 30)) as pool:
            jobs = pool.imap_unordered(func=spawn_runner, iterable=plan.spawn_runner_configs)
            for _ in range(len(plan.spawn_runner_configs)):
                try:
                    instance_id = next(jobs)
                except (RunnerError, PlatformApiError):
                    logger.exception("Failed to spawn a runner.")
                except StopIteration:
                    break
                else:
                    instance_id_list.append(instance_id)
        return tuple(instance_id_list)

    def _spawn_prespawn_runners(
        self, plan: _PreaspawnReconcileActionPlan
    ) -> tuple[InstanceID, ...]:
        """Spawn runners in a prespawn manner."""
        instance_id_list = []
        spawn_runner_configs: list[_SpawnRunnerConfig] = []
        prespawn_config = cast(PrespawnConfig, self._algorithm_config)
        for _ in range(plan.quantity):
            instance_id = InstanceID.build(
                self._cloud.name_prefix,
                reactive=False,
            )
            metadata = RunnerMetadata(platform_name=self._platform.platform)
            runner_context, runner = self._platform.get_runner_context(
                instance_id=instance_id, metadata=metadata, labels=self._config.labels
            )
            spawn_runner_configs.append(
                _SpawnRunnerConfig(
                    platform_provider=self._platform,
                    cloud_provider=self._cloud,
                    instance_id=instance_id,
                    algorithm=ReconcileAlgorithm.PRESPAWN,
                    vm_config=OpenStackServerConfig(
                        image=prespawn_config.vm_image,
                        flavor=prespawn_config.vm_flavor,
                    ),
                    runner=runner,
                    runner_context=runner_context,
                    runner_metadata=metadata,
                )
            )
        with multiprocessing.Pool(processes=min(plan.quantity, 30)) as pool:
            jobs = pool.imap_unordered(func=spawn_runner, iterable=spawn_runner_configs)
            for _ in range(plan.quantity):
                try:
                    instance_id = next(jobs)
                except (RunnerError, PlatformApiError):
                    logger.exception("Failed to spawn a runner.")
                except StopIteration:
                    break
                else:
                    instance_id_list.append(instance_id)
        return tuple(instance_id_list)


def _build_runner_metadata(job_url: str) -> RunnerMetadata:
    """Build runner metadata from the job url."""
    parsed_url = urlparse(job_url)
    # We expect the netloc to contain github.com, otherwise this function will fail,
    # as will use jobmanager code to handle github runners.
    if "github.com" in parsed_url.netloc:
        return RunnerMetadata()

    # From here on jobmanager. For now we just regex on the url to check if it is the url
    # of a runner.
    match_result = re.match(r"^(.*)/v1/jobs/(\d+)$", parsed_url.path)
    if not match_result:
        logger.error("Invalid URL for a job. url: %s", job_url)
        raise ValueError(f"Invalid format for job url {job_url}")
    base_url = parsed_url._replace(path=match_result.group(1)).geturl()
    return RunnerMetadata(platform_name=Platform.LAUNCHPAD, url=base_url)


@dataclass
class _SpawnRunnerConfig:
    """Configuration for spawning a runner.

    Attributes:
        platform_provider: The runner platform service provider.
        cloud_provider: The runner cloud service provider.
        instance_id: The instance ID to use on the cloud provider.
        algorithm: The algorithm in which the runner will be created.
        vm_config: The configuration for the VM.
        runner: The runner that will be spawned.
        runner_context: The metadata in which the runner will be created.
        runner_metadata: Metadata about the runner and it's platform.
    """

    platform_provider: SupportsPlatformProvider
    cloud_provider: SupportsCloudProvider
    instance_id: InstanceID
    algorithm: ReconcileAlgorithm
    vm_config: OpenStackServerConfig
    runner: SelfHostedRunner
    runner_context: RunnerContext
    runner_metadata: RunnerMetadata


# After a runner is created, there will be as many health checks as
# elements in this variable. The elements in the tuple represent
# the time waiting before each health check against the platform provider.
RUNNER_CREATION_WAITING_TIMES = (60, 60, 120, 240, 480)
JOB_PICKUP_TIMEOUT = 60 * 10


def spawn_runner(config: _SpawnRunnerConfig) -> InstanceID:
    """Spawn runner.

    This function is to be called from a multiprocessed process, i.e. multiprocessing.Pool.

    Args:
        config: The configuration for spawning a runner.

    Raises:
        RunnerError: if there was any error during the creation of the runner.

    Returns:
        The created instance ID.
    """
    # Update the runner id if necessary
    if not config.runner_metadata.runner_id:
        config.runner_metadata.runner_id = str(config.runner.id)

    runner_identity = RunnerIdentity(
        instance_id=config.instance_id, metadata=config.runner_metadata
    )
    logger.info(
        "Spawning %s VM with ID: %s, image: %s, flavor: %s",
        runner_identity.instance_id,
        config.algorithm,
        config.vm_config.image,
        config.vm_config.flavor,
    )
    vm = config.cloud_provider.create_vm(
        runner_identity=runner_identity, vm_config=config.vm_config
    )
    logger.info("Created VM: %s", vm.instance_id)

    if config.algorithm != ReconcileAlgorithm.REACTIVE:
        return config.instance_id

    try:
        _wait_for(
            callable=lambda: config.platform_provider.get_runner(runner_identity=runner_identity),
            timeout=10 * 60,
            interval=60,
            interval_log="Waiting for runner to be created",
            ignore_exception=PlatformApiError,
        )
    except TimeoutError:
        logger.warning(
            "Deleting runner %s from platform after creation failed", config.instance_id
        )
        config.platform_provider.delete_runner(runner_identity=runner_identity)
        raise

    try:
        _wait_for(
            callable=lambda: config.platform_provider.get_job(),
            timeout=10 * 60,
            interval=60,
            interval_log="Waiting for Job to be picked up",
        )
    except TimeoutError:
        logger.warning(
            "Deleting runner %s from platform after job pickup failed", config.instance_id
        )
        config.platform_provider.delete_runner(runner_identity=runner_identity)
        raise

    return config.instance_id


def _wait_for(
    callable: Callable,
    timeout: int,
    interval: int = 60,
    interval_log: str = "",
    ignore_exception: Type[Exception] | None = None,
):
    """Wait for a callable to return Truthy value within timeout.

    Args:
        callable: The function that should return a truthy value within timeout.
        timeout: Timeout in seconds for the callable to be truthy.
        interval: Interval in seconds between checks.
        interval_log: Log message to print at each interval.
        ignore_exception: Exception type to ignore during the wait.
    """
    start_time = time.time()
    while time.time() - start_time > timeout:
        logger.info(interval_log)
        if ignore_exception:
            try:
                result = callable()
                if not result:
                    continue
                return result
            except ignore_exception:
                pass
            time.sleep(interval)
        else:
            result = callable()
            if not result:
                continue
            return result
    return TimeoutError("Timed out waiting for callable to be true")
