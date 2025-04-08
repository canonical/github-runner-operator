# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base classes and APIs for platform providers."""

import abc
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Iterable  # pylint: disable=unused-import

from pydantic import HttpUrl

from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


class PlatformError(Exception):
    """Base class for all platform provider errors."""


class JobNotFoundError(PlatformError):
    """Represents an error when the job could not be found on the platform."""


class PlatformProvider(abc.ABC):
    """Base class for a Platform Provider."""

    @abc.abstractmethod
    def get_runners(
        self, states: "Iterable[PlatformRunnerState] | None" = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.
        """

    @abc.abstractmethod
    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners.

        Args:
            runners: list of runners to delete.
        """

    @abc.abstractmethod
    def get_runner_token(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: TODO.
            labels: Labels for the runner.
        """

    @abc.abstractmethod
    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.
        """

    @abc.abstractmethod
    def check_job_been_picked_up(self, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
        """

    @abc.abstractmethod
    def get_job_info(self, repository: str, workflow_run_id: str, runner: InstanceID) -> "JobInfo":
        """Get the Job info from the provider.

        Args:
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.
        """


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
        if runner.status == GitHubRunnerStatus.ONLINE:
            if not runner.busy:
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
