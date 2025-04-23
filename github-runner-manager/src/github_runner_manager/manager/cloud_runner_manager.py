# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface of manager of runner instance on clouds."""

import abc
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Iterator, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, NonNegativeFloat

from github_runner_manager.manager.models import InstanceID, RunnerContext, RunnerMetadata

logger = logging.getLogger(__name__)


class HealthState(Enum):
    """Health state of the runners.

    Attributes:
        HEALTHY: The runner is healthy.
        UNHEALTHY: The runner is not healthy.
        UNKNOWN: Unable to get the health state.
    """

    HEALTHY = auto()
    UNHEALTHY = auto()
    UNKNOWN = auto()

    @staticmethod
    def from_value(health: bool | None) -> "HealthState":
        """Create from a health value.

        Args:
            health: The health value as boolean or None.

        Returns:
            The health state.
        """
        if health is None:
            return HealthState.UNKNOWN
        return HealthState.HEALTHY if health else HealthState.UNHEALTHY


class CloudRunnerState(str, Enum):
    """Represent state of the instance hosting the runner.

    Attributes:
        CREATED: The instance is created.
        ACTIVE: The instance is active and running.
        DELETED: The instance is deleted.
        ERROR: The instance has encountered error and not running.
        STOPPED: The instance has stopped.
        UNKNOWN: The state of the instance is not known.
        UNEXPECTED: An unknown state not accounted by the developer is encountered.
    """

    CREATED = auto()
    ACTIVE = auto()
    DELETED = auto()
    ERROR = auto()
    STOPPED = auto()
    UNKNOWN = auto()
    UNEXPECTED = auto()

    # Exclude from coverage as not much value for testing this object conversion.
    @staticmethod
    def from_openstack_server_status(  # pragma: no cover
        openstack_server_status: str,
    ) -> "CloudRunnerState":
        """Create from openstack server status.

        The openstack server status are documented here:
        https://docs.openstack.org/api-guide/compute/server_concepts.html

        Args:
            openstack_server_status: Openstack server status.

        Returns:
            The state of the runner.
        """
        state = CloudRunnerState.UNEXPECTED
        match openstack_server_status:
            case "BUILD":
                state = CloudRunnerState.CREATED
            case "REBUILD":
                state = CloudRunnerState.CREATED
            case "ACTIVE":
                state = CloudRunnerState.ACTIVE
            case "ERROR":
                state = CloudRunnerState.ERROR
            case "STOPPED":
                state = CloudRunnerState.STOPPED
            case "DELETED":
                state = CloudRunnerState.DELETED
            case "UNKNOWN":
                state = CloudRunnerState.UNKNOWN
            case _:
                state = CloudRunnerState.UNEXPECTED
        return state


class CloudInitStatus(str, Enum):
    """Represents the state of cloud-init script.

    The cloud init script is used to launch ephemeral GitHub runners. If the script is being
    initialized, GitHub runner is listening for jobs or GitHub runner is running the job, the
    cloud-init script should report "running" status.

    Refer to the official documentation on cloud-init status:
    https://cloudinit.readthedocs.io/en/latest/howto/status.html.

    Attributes:
        NOT_STARTED: The cloud-init script has not yet been started.
        RUNNING: The cloud-init script is running.
        DONE: The cloud-init script has completed successfully.
        ERROR: There was an error while running the cloud-init script.
        DEGRADED: There was a non-critical issue while running the cloud-inits script.
        DISABLED: Cloud init was disabled by other system configurations.
    """

    NOT_STARTED = "not started"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    DEGRADED = "degraded"
    DISABLED = "disabled"


@dataclass
class CloudRunnerInstance:
    """Information on the runner on the cloud.

    Attributes:
        name: Name of the instance hosting the runner.
        instance_id: ID of the instance.
        metadata: Metadata of the runner.
        health: Health state of the runner.
        state: State of the instance hosting the runner.
    """

    name: str
    instance_id: InstanceID
    metadata: RunnerMetadata
    health: HealthState
    state: CloudRunnerState


class PreJobMetrics(BaseModel):
    """Metrics for the pre-job phase of a runner.

    Attributes:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        workflow: The workflow name.
        workflow_run_id: The workflow run id.
        repository: The repository path in the format '<owner>/<repo>'.
        event: The github event.
    """

    timestamp: NonNegativeFloat
    workflow: str
    workflow_run_id: str
    repository: str = Field(None, regex=r"^.+/.+$")
    event: str


class PostJobStatus(str, Enum):
    """The status of the post-job phase of a runner.

    Attributes:
        NORMAL: Represents a normal post-job.
        ABNORMAL: Represents an error with post-job.
        REPO_POLICY_CHECK_FAILURE: Represents an error with repo-policy-compliance check.
    """

    NORMAL = "normal"
    ABNORMAL = "abnormal"
    REPO_POLICY_CHECK_FAILURE = "repo-policy-check-failure"


class CodeInformation(BaseModel):
    """Information about a status code.

    Attributes:
        code: The status code.
    """

    code: int


class PostJobMetrics(BaseModel):
    """Metrics for the post-job phase of a runner.

    Attributes:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        status: The status of the job.
        status_info: More information about the status.
    """

    timestamp: NonNegativeFloat
    status: PostJobStatus
    status_info: Optional[CodeInformation]


class RunnerMetrics(BaseModel):
    """Metrics for a runner.

    Attributes:
        instance_id: The name of the runner.
        metadata: Runner metadata.
        installation_start_timestamp: The UNIX time stamp of the time at which the runner
            installation started.
        installed_timestamp: The UNIX time stamp of the time at which the runner was installed.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
    """

    instance_id: InstanceID
    metadata: RunnerMetadata
    installation_start_timestamp: NonNegativeFloat | None
    installed_timestamp: NonNegativeFloat
    pre_job: PreJobMetrics | None
    post_job: PostJobMetrics | None


class CloudRunnerManager(abc.ABC):
    """Manage runner instance on cloud.

    Attributes:
        name_prefix: The name prefix of the self-hosted runners.
    """

    @property
    @abc.abstractmethod
    def name_prefix(self) -> str:
        """Get the name prefix of the self-hosted runners."""

    @abc.abstractmethod
    def create_runner(
        self,
        instance_id: InstanceID,
        metadata: RunnerMetadata,
        runner_context: RunnerContext,
    ) -> CloudRunnerInstance:
        """Create a self-hosted runner.

        Args:
            instance_id: Instance ID for the runner.
            metadata: Runner Metadata.
            runner_context: Context information needed to spawn the runner.
        """

    @abc.abstractmethod
    def get_runners(self, states: Sequence[CloudRunnerState]) -> Tuple[CloudRunnerInstance]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.
        """

    @abc.abstractmethod
    def delete_runner(self, instance_id: InstanceID, remove_token: str) -> RunnerMetrics | None:
        """Delete self-hosted runner.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.
        """

    @abc.abstractmethod
    def flush_runners(self, remove_token: str, busy: bool = False) -> Iterator[RunnerMetrics]:
        """Stop all runners.

        Args:
            remove_token: The GitHub remove token for removing runners.
            busy: If false, only idle runners are removed. If true, both idle and busy runners are
                removed.
        """

    @abc.abstractmethod
    def cleanup(self, remove_token: str) -> Iterable[RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Perform health check on runner and delete the runner if it fails.

        Args:
            remove_token: The GitHub remove token for removing runners.
        """
