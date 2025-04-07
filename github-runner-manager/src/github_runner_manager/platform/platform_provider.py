# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base classes and APIs for platform providers."""

import abc
from enum import Enum, auto
from typing import Iterable  # pylint: disable=unused-import

from github_runner_manager.manager.models import InstanceID
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


# Work in progress. This will be the parent class (and API) for GitHub and JobManager.
class PlatformProvider(abc.ABC):  # pylint: disable=too-few-public-methods
    """Base class for a Provider."""

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
        """Delete runners in GitHub.

        Args:
            runners: list of runners to delete.
        """

    @abc.abstractmethod
    def get_runner_token(
        self, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.
        """

    @abc.abstractmethod
    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.
        """


# Pending to review the coupling of this class with GitHub
class PlatformRunnerState(str, Enum):
    """State of the self-hosted runner on GitHub.

    Attributes:
        BUSY: Runner is working on a job assigned by GitHub.
        IDLE: Runner is waiting to take a job or is running pre-job tasks (i.e.
            repo-policy-compliance check).
        OFFLINE: Runner is not connected to GitHub.
    """

    BUSY = auto()
    IDLE = auto()
    OFFLINE = auto()

    @staticmethod
    def from_runner(runner: SelfHostedRunner) -> "PlatformRunnerState":
        """Construct the object from GtiHub runner information.

        Args:
            runner: Information on the GitHub self-hosted runner.

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
