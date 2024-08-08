# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

from enum import Enum
from typing import Sequence

from charm_state import GithubPath
from github_client import GithubClient
from github_type import GitHubRunnerStatus, SelfHostedRunner


class GithubRunnerState(str, Enum):
    """State of the runner on GitHub."""

    BUSY = "busy"
    IDLE = "idle"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    @staticmethod
    def from_runner(runner: SelfHostedRunner) -> "GithubRunnerState":
        """Construct the object from GtiHub runner information.

        Args:
            runner: Information on the GitHub self-hosted runner.

        Returns:
            The state of runner.
        """
        state = GithubRunnerState.OFFLINE
        if runner.status == GitHubRunnerStatus.ONLINE:
            if runner.busy:
                state = GithubRunnerState.BUSY
            if not runner.busy:
                state = GithubRunnerState.IDLE
        return state


class GithubRunnerManager:
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, token: str, path: GithubPath):
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
        self, states: Sequence[GithubRunnerState] | None = None
    ) -> tuple[SelfHostedRunner]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Information on the runners.
        """
        runner_list = self.github.get_runner_github_info(self._path)
        return tuple(
            runner
            for runner in runner_list
            if runner.name.startswith(self._prefix)
            and GithubRunnerManager._filter_runner_state(runner, states)
        )

    def delete_runners(self, states: Sequence[GithubRunnerState] | None = None) -> None:
        """Delete the self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are deleted.

        Returns:
            Information on the runners.
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
    def _filter_runner_state(
        runner: SelfHostedRunner, states: Sequence[GithubRunnerState] | None
    ) -> bool:
        """Filter the runner by the state.

        Args:
            states: Filter the runners for these states. If None, return true.

        Returns:
            True if the runner is in one of the state, else false.
        """
        if states is None:
            return True
        return GithubRunnerState.from_runner(runner) in states
