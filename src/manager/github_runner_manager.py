# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

from enum import Enum, auto
from typing import Iterable

from charm_state import GitHubPath
from github_client import GithubClient
from github_type import GitHubRunnerStatus, SelfHostedRunner


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


class GitHubRunnerManager:
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, token: str, path: GitHubPath):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            token: The GitHub personal access token to access the GitHub API.
            path: The GitHub repository or organization to register the runners under.
        """
        self._prefix = prefix
        self._path = path
        self.github = GithubClient(token)

    def get_runners(
        self, states: Iterable[GitHubRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Information on the runners.
        """
        runner_list = self.github.get_runner_github_info(self._path)
        state_set = set(states)
        return tuple(
            runner
            for runner in runner_list
            if runner.name.startswith(self._prefix)
            and GitHubRunnerManager._is_runner_in_state(runner, state_set)
        )

    def delete_runners(self, states: Iterable[GitHubRunnerState] | None = None) -> None:
        """Delete the self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are deleted.
        """
        runner_list = self.get_runners(states)
        for runner in runner_list:
            self.github.delete_runner(self._path, runner.id)

    def get_registration_token(self) -> str:
        """Get registration token from GitHub.

        This token is used for registering self-hosted runners.

        Returns:
            The registration token.
        """
        return self.github.get_runner_registration_token(self._path)

    def get_removal_token(self) -> str:
        """Get removal token from GitHub.

        This token is used for removing self-hosted runners.

        Returns:
            The removal token.
        """
        return self.github.get_runner_remove_token(self._path)

    @staticmethod
    def _is_runner_in_state(
        runner: SelfHostedRunner, states: set[GitHubRunnerState] | None
    ) -> bool:
        """Check that the runner is in one of the states provided.

        Args:
            runner: Runner to filter.
            states: States in which to check the runner belongs to.

        Returns:
            True if the runner is in one of the state, else false.
        """
        if states is None:
            return True
        return GitHubRunnerState.from_runner(runner) in states
