# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface of manager of runner instance on clouds."""

import abc
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Optional, Protocol, Sequence

from pydantic import BaseModel, Field, NonNegativeFloat

from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)

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


class VMState(str, Enum):
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
    ) -> "VMState":
        """Create from openstack server status.

        The openstack server status are documented here:
        https://docs.openstack.org/api-guide/compute/server_concepts.html

        Args:
            openstack_server_status: Openstack server status.

        Returns:
            The state of the runner.
        """
        state = VMState.UNEXPECTED
        match openstack_server_status:
            case "BUILD":
                state = VMState.CREATED
            case "REBUILD":
                state = VMState.CREATED
            case "ACTIVE":
                state = VMState.ACTIVE
            case "ERROR":
                state = VMState.ERROR
            case "STOPPED":
                state = VMState.STOPPED
            case "DELETED":
                state = VMState.DELETED
            case "UNKNOWN":
                state = VMState.UNKNOWN
            case _:
                state = VMState.UNEXPECTED
        return state


@dataclass
class VM:
    """Information on the runner on the cloud.

    Attributes:
        instance_id: VM instance identifier (NOT VM UUID).
        metadata: Metadata associated with the VM.
        state: The VM state.
        created_at: Creation time of the runner in the cloud provider.
    """

    instance_id: InstanceID
    metadata: RunnerMetadata
    state: VMState
    created_at: datetime

    def is_older_than(self, seconds: float) -> bool:
        """Check if the cloud instance is older than the provided args.

        Args:
            seconds: The seconds to check if the machine is older than.

        Returns:
            True is the machine is older than the seconds provided.
        """
        now = datetime.now(timezone.utc)
        return (now - self.created_at).total_seconds() > seconds


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


class RunnerMetrics(Protocol):
    """Metrics for a runner.

    Attributes:
        metadata: The metadata of the VM in which the metrics are fetched from.
        instance_id: The instance ID of the VM in which the metrics are fetched from.
        installation_start_timestamp: The UNIX timestamp of in which the VM setup started.
        installation_end_timestamp: The UNIX timestamp of in which the VM setup ended.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
    """

    @property
    def pre_job(self) -> PreJobMetrics | None:
        """Metrics from the pre-job phase."""

    @property
    def post_job(self) -> PostJobMetrics | None:
        """Metrics from the post-job phase."""

    @property
    # Ignore no return implementation because this is a protocol class.
    def metadata(self) -> RunnerMetadata:  # type: ignore
        """Metadata of the VM in which the metrics are fetche from."""

    @property
    # Ignore no return implementation because this is a protocol class.
    def instance_id(self) -> InstanceID:  # type: ignore
        """Instance ID of the VM in which the metrics are fetched from."""

    @property
    # Ignore no return implementation because this is a protocol class.
    def installation_start_timestamp(self) -> NonNegativeFloat:  # type: ignore
        """UNIX timestamp of in which the VM setup started."""

    @property
    def installation_end_timestamp(self) -> NonNegativeFloat | None:
        """UNIX timestamp of in which the VM setup ended."""


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
        runner_identity: RunnerIdentity,
        runner_context: RunnerContext,
    ) -> VM:
        """Create a self-hosted runner.

        Args:
            runner_identity: Identity of the runner to create.
            runner_context: Context information needed to spawn the runner.
        """

    @abc.abstractmethod
    def get_vms(self) -> Sequence[VM]:
        """Get cloud self-hosted runners."""

    @abc.abstractmethod
    # Abstract methods do not have a return value, ignore the docstring error DCO031
    def delete_vms(self, instance_ids: Sequence[InstanceID]) -> list[InstanceID]:
        """Delete cloud VM instances.

        Args:
            instance_ids: The ID of the VMs to request deletion.

        Returns:
            The deleted instance IDs.
        """  # noqa: DCO031

    @abc.abstractmethod
    # Abstract methods do not have a return value, ignore the docstring error DCO031
    def extract_metrics(self, instance_ids: Sequence[InstanceID]) -> list[RunnerMetrics]:
        """Extract metrics from cloud VMs.

        Args:
            instance_ids: The VM instance IDs to fetch the metrics from.

        Returns:
            The fetched runner metrics.
        """  # noqa: DCO031

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Cleanup runner dangling resources on the cloud."""
