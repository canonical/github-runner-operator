# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""TODO."""

from enum import Enum, auto

from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


# Work in progress.
class PlatformProvider:  # pylint: disable=too-few-public-methods
    """TODO."""


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
