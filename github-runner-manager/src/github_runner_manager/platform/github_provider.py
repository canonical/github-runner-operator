# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

from typing import Iterable

from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.platform.platform_provider import PlatformProvider, PlatformRunnerState
from github_runner_manager.types_.github import SelfHostedRunner


class GitHubRunnerPlatform(PlatformProvider):
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, github_configuration: GitHubConfiguration):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration information.
        """
        self._prefix = prefix
        self._path = github_configuration.path
        self._client = GithubClient(github_configuration.token)

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Information on the runners.
        """
        runner_list = self._client.get_runner_github_info(self._path, self._prefix)

        if states is None:
            return tuple(runner_list)

        state_set = set(states)
        return tuple(
            runner
            for runner in runner_list
            if GitHubRunnerPlatform._is_runner_in_state(runner, state_set)
        )

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners in GitHub.

        Args:
            runners: list of runners to delete.
        """
        for runner in runners:
            self._client.delete_runner(self._path, runner.id)

    def get_runner_token(
        self, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token and the runner.
        """
        return self._client.get_runner_registration_jittoken(self._path, instance_id, labels)

    def get_removal_token(self) -> str:
        """Get removal token from GitHub.

        This token is used for removing self-hosted runners.

        Returns:
            The removal token.
        """
        return self._client.get_runner_remove_token(self._path)

    @staticmethod
    def _is_runner_in_state(runner: SelfHostedRunner, states: set[PlatformRunnerState]) -> bool:
        """Check that the runner is in one of the states provided.

        Args:
            runner: Runner to filter.
            states: States in which to check the runner belongs to.

        Returns:
            True if the runner is in one of the state, else false.
        """
        return PlatformRunnerState.from_runner(runner) in states
