# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base classes and APIs for platform providers."""

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from pydantic import HttpUrl

from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


class PlatformError(Exception):
    """Base class for all platform provider errors."""


class JobNotFoundError(PlatformError):
    """Represents an error when the job could not be found on the platform."""


class DeleteRunnerBusyError(PlatformError):
    """Error when deleting a runner that cannot be deleted as it could be busy."""


class PlatformApiError(PlatformError):
    """Represents an error when one of the Platform APIs returns an error."""


class TokenError(PlatformError):
    """Represents an error when the token is invalid or has not enough permissions."""


class PlatformProvider(abc.ABC):
    """Base class for a Platform Provider."""

    @abc.abstractmethod
    def get_runner_health(self, runner_identity: RunnerIdentity) -> "PlatformRunnerHealth":
        """Get health information on self-hosted runner.

        Args:
            runner_identity: Identity of the runner.
        """

    @abc.abstractmethod
    def get_runners_health(
        self, requested_runners: list[RunnerIdentity]
    ) -> "RunnersHealthResponse":
        """Get information from the requested runners health.

        This method returns a RunnersHealthResponse object that contains three lists with runners,
        none of them necessarily in the same order as the input argument:
         - requested_runners: Runners for which a health check succeeded with the requested
           information.
         - failed_requested_runners: Runners for which the health check failed, and may succeed
           if retrying.
         - non_requested_runners: List of runners in the platform provider that were not requested.
           This is an optional response from the provider. This may be useful to clean resources
           in the platform provider.

        Args:
            requested_runners: List of runners to get health information for.
        """

    @abc.abstractmethod
    def delete_runners(self, runner_ids: list[str], platform: str = "github") -> list[str]:
        """Delete runners.

        Args:
            runner_ids: Runner IDs to delete.
            platform: The Platform in which to delete the runners in.
        """

    @abc.abstractmethod
    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get a one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            metadata: Metadata for the runner.
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.
        """

    @abc.abstractmethod
    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            metadata: Metadata for the runner.
            job_url: The URL of the job.
        """

    @abc.abstractmethod
    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> "JobInfo":
        """Get the Job info from the provider.

        Raises JobNotFoundError if the job was not found.

        Args:
            metadata: metadata. Always needed at least for the platform selection.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.
        """


@dataclass
class RunnersHealthResponse:
    """Response for the get_runners_health.

    See information in the method PlatformProvider.get_runners_health
    The order or the runners in the lists is arbitrary.

    Attributes:
        requested_runners: Health information for the requested runners.
        failed_requested_runners: Requested runners for which the health check request failed,
            and was not possible to get information.
        non_requested_runners: Optional list of runners for which the health check was not
            requested.
    """

    requested_runners: "list[PlatformRunnerHealth]" = field(default_factory=list)
    failed_requested_runners: "list[RunnerIdentity]" = field(default_factory=list)
    non_requested_runners: "list[RunnerIdentity]" = field(default_factory=list)

    def append(self, other: "RunnersHealthResponse") -> None:
        """Append the other RunnersHealthResponse to the current object.

        Args:
            other: Other RunnersHealthResponse.
        """
        self.requested_runners += other.requested_runners
        self.failed_requested_runners += other.failed_requested_runners
        self.non_requested_runners += other.non_requested_runners


@dataclass(order=True)
class PlatformRunnerHealth:
    """Information about the health of a platform runner.

    A runner can be online if it is connected to the platform. If the platform
    does not provide that information, any runner that has connected to the platform
    should be considered online. It is deletable if there is no risk in deleting the
    compute instance, and busy if it is currently executing a job in the platform
    manager.

    Attributes:
        identity: Identity of the runner.
        online: Whether the runner is online.
        busy: Whether the runner is busy.
        deletable: Whether the runner is deletable.
        runner_in_platform: Whether the runner is in the platform.
    """

    identity: RunnerIdentity
    online: bool
    busy: bool
    deletable: bool
    runner_in_platform: bool = True


# Pending to review the coupling of this class with GitHub
class PlatformRunnerState(str, Enum):
    """State of the self-hosted runner.

    Attributes:
        BUSY: Runner is working on a job assigned.
        IDLE: Runner is waiting to take a job or is running pre-job tasks (i.e.
            repo-policy-compliance check).
        OFFLINE: Runner is not connected.
    """

    BUSY = auto()
    IDLE = auto()
    OFFLINE = auto()

    @staticmethod
    def from_runner(runner: SelfHostedRunner) -> "PlatformRunnerState":
        """Construct the object from runner information.

        Args:
            runner: Information on the self-hosted runner.

        Returns:
            The state of runner.
        """
        state = PlatformRunnerState.OFFLINE
        # A runner that is busy and offline is possible.
        if runner.busy:
            state = PlatformRunnerState.BUSY
        if runner.status == GitHubRunnerStatus.ONLINE and not runner.busy:
            state = PlatformRunnerState.IDLE
        return state

    @staticmethod
    def from_platform_health(health: PlatformRunnerHealth) -> "PlatformRunnerState":
        """Construct the object from runner information.

        Args:
            health: health information from a runner.

        Returns:
            The state of runner.
        """
        state = PlatformRunnerState.OFFLINE

        if health.deletable:
            state = PlatformRunnerState.OFFLINE
        elif health.busy:
            state = PlatformRunnerState.BUSY
        elif health.online:
            state = PlatformRunnerState.IDLE
        return state


@dataclass
class JobInfo:
    """Stats for a job on a platform.

    Attributes:
        created_at: The time the job was created.
        started_at: The time the job was started.
        conclusion: The end result of a job.
    """

    created_at: datetime
    started_at: datetime
    # A str until we realise a common pattern, use a simple str
    conclusion: str | None
