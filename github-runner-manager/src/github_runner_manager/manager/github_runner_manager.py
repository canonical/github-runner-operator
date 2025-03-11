# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

from enum import Enum, auto
from typing import Iterable

from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


class GitHubRunnerState(str, Enum):
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
    def from_runner(runner: SelfHostedRunner) -> "GitHubRunnerState":
        """Construct the object from GtiHub runner information.

        Args:
            runner: Information on the GitHub self-hosted runner.

        Returns:
            The state of runner.
        """
        state = GitHubRunnerState.OFFLINE
        # A runner that is busy and offline is possible.
        if runner.busy:
            state = GitHubRunnerState.BUSY
        if runner.status == GitHubRunnerStatus.ONLINE:
            if not runner.busy:
                state = GitHubRunnerState.IDLE
        return state


# Thin wrapper around the GitHub Client. Not much value in unit testing.
class GitHubRunnerManager:  # pragma: no cover
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, github_configuration: GitHubConfiguration):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration information.
        """
        self._prefix = prefix
        self._path = github_configuration.path
        self.github = GithubClient(github_configuration.token)

    def get_runners(
        self, states: Iterable[GitHubRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Information on the runners.
        """
        runner_list = self.github.get_runner_github_info(self._path, self._prefix)

        if states is None:
            return tuple(runner_list)

        state_set = set(states)
        return tuple(
            runner
            for runner in runner_list
            if GitHubRunnerManager._is_runner_in_state(runner, state_set)
        )

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners in GitHub.

        Args:
            runners: list of runners to delete.
        """
        for runner in runners:
            self.github.delete_runner(self._path, runner.id)

    def get_registration_jittoken(self, instance_id: InstanceID, labels: list[str]) -> str:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token.
        """
        return self.github.get_runner_registration_jittoken(self._path, instance_id, labels)

    def get_removal_token(self) -> str:
        """Get removal token from GitHub.

        This token is used for removing self-hosted runners.

        Returns:
            The removal token.
        """
        return self.github.get_runner_remove_token(self._path)

    @staticmethod
    def _is_runner_in_state(runner: SelfHostedRunner, states: set[GitHubRunnerState]) -> bool:
        """Check that the runner is in one of the states provided.

        Args:
            runner: Runner to filter.
            states: States in which to check the runner belongs to.

        Returns:
            True if the runner is in one of the state, else false.
        """
        return GitHubRunnerState.from_runner(runner) in states
