# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import random
import secrets
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence
from unittest.mock import MagicMock

from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    InstanceId,
)
from github_runner_manager.manager.github_runner_manager import GitHubRunnerState
from github_runner_manager.metrics.runner import RunnerMetrics

from charm_state import GitHubPath
from github_client import GithubClient
from github_type import GitHubRunnerStatus, SelfHostedRunner
from tests.unit.mock import MockGhapiClient


@dataclass
class MockRunner:
    """Mock of a runner.

    Attributes:
        name: The name of the runner.
        instance_id: The instance id of the runner.
        cloud_state: The cloud state of the runner.
        github_state: The github state of the runner.
        health: The health state of the runner.
    """

    name: str
    instance_id: InstanceId
    cloud_state: CloudRunnerState
    github_state: GitHubRunnerState
    health: bool

    def __init__(self, name: str):
        """Construct the object.

        Args:
            name: The name of the runner.
        """
        self.name = name
        self.instance_id = secrets.token_hex(6)
        self.cloud_state = CloudRunnerState.ACTIVE
        self.github_state = GitHubRunnerState.IDLE
        self.health = True

    def to_cloud_runner(self) -> CloudRunnerInstance:
        """Construct CloudRunnerInstance from this object.

        Returns:
            The CloudRunnerInstance instance.
        """
        return CloudRunnerInstance(
            name=self.name,
            instance_id=self.instance_id,
            health=self.health,
            state=self.cloud_state,
        )


@dataclass
class SharedMockRunnerManagerState:
    """State shared by mock runner managers.

    For sharing the mock runner states between MockCloudRunnerManager and MockGitHubRunnerManager.

    Attributes:
        runners: The runners.
    """

    runners: dict[InstanceId, MockRunner]

    def __init__(self):
        """Construct the object."""
        self.runners = {}


class MockCloudRunnerManager(CloudRunnerManager):
    """Mock of CloudRunnerManager.

    Metrics is not supported in this mock.

    Attributes:
        name_prefix: The naming prefix for runners managed.
        prefix: The naming prefix for runners managed.
        state: The shared state between mocks runner managers.
    """

    def __init__(self, state: SharedMockRunnerManagerState):
        """Construct the object.

        Args:
            state: The shared state between cloud and github runner managers.
        """
        self.prefix = f"mock_{secrets.token_hex(4)}"
        self.state = state

    @property
    def name_prefix(self) -> str:
        """Get the name prefix of the self-hosted runners."""
        return self.prefix

    def create_runner(self, registration_token: str) -> InstanceId:
        """Create a self-hosted runner.

        Args:
            registration_token: The GitHub registration token for registering runners.

        Returns:
            The instance id of the runner created.
        """
        name = f"{self.name_prefix}-{secrets.token_hex(6)}"
        runner = MockRunner(name)
        self.state.runners[runner.instance_id] = runner
        return runner.instance_id

    def get_runner(self, instance_id: InstanceId) -> CloudRunnerInstance | None:
        """Get a self-hosted runner by instance id.

        Args:
            instance_id: The instance id.

        Returns:
            The runner instance if found else None.
        """
        runner = self.state.runners.get(instance_id, None)
        if runner is not None:
            return runner.to_cloud_runner()
        return None

    def get_runners(
        self, states: Sequence[CloudRunnerState] | None = None
    ) -> tuple[CloudRunnerInstance, ...]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.

        Returns:
            The list of runner instances.
        """
        if states is None:
            states = [member.value for member in CloudRunnerState]

        state_set = set(states)
        return tuple(
            runner.to_cloud_runner()
            for runner in self.state.runners.values()
            if runner.cloud_state in state_set
        )

    def delete_runner(self, instance_id: InstanceId, remove_token: str) -> RunnerMetrics | None:
        """Delete self-hosted runner.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.

        Returns:
            Any runner metrics produced during deletion.
        """
        runner = self.state.runners.pop(instance_id, None)
        if runner is not None:
            return iter([MagicMock()])
        return iter([])

    def flush_runners(self, remove_token: str, busy: bool = False) -> Iterator[RunnerMetrics]:
        """Stop all runners.

        Args:
            remove_token: The GitHub remove token for removing runners.
            busy: If false, only idle runners are removed. If true, both idle and busy runners are
                removed.

        Returns:
            Any runner metrics produced during flushing.
        """
        if busy:
            self.state.runners = {}
        else:
            self.state.runners = {
                instance_id: runner
                for instance_id, runner in self.state.runners.items()
                if runner.github_state == GitHubRunnerState.BUSY
            }
        return iter([MagicMock()])

    def cleanup(self, remove_token: str) -> Iterator[RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Perform health check on runner and delete the runner if it fails.

        Args:
            remove_token: The GitHub remove token for removing runners.

        Returns:
            Any runner metrics produced during cleanup.
        """
        # Do nothing in mocks.
        return iter([MagicMock()])


class MockGitHubRunnerManager:
    """Mock of GitHubRunnerManager.

    Attributes:
        github: The GitHub client.
        name_prefix: The naming prefix for runner managed.
        state: The shared state between mock runner managers.
        path: The GitHub path to register the runners under.
    """

    def __init__(self, name_prefix: str, path: GitHubPath, state: SharedMockRunnerManagerState):
        """Construct the object.

        Args:
            name_prefix: The naming prefix for runner managed.
            path: The GitHub path to register the runners under.
            state: The shared state between mock runner managers.
        """
        self.github = GithubClient("mock_token")
        self.github._client = MockGhapiClient("mock_token")
        self.name_prefix = name_prefix
        self.state = state
        self.path = path

    def get_registration_token(self) -> str:
        """Get the registration token for registering runners on GitHub.

        Returns:
            The registration token.
        """
        return "mock_registration_token"

    def get_removal_token(self) -> str:
        """Get the remove token for removing runners on GitHub.

        Returns:
            The remove token.
        """
        return "mock_remove_token"

    def get_runners(
        self, github_states: Iterable[GitHubRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get the runners.

        Args:
            github_states: The states to filter for.

        Returns:
            List of runners.
        """
        if github_states is None:
            github_states = [member.value for member in GitHubRunnerState]

        github_state_set = set(github_states)
        return tuple(
            SelfHostedRunner(
                busy=runner.github_state == GitHubRunnerState.BUSY,
                id=random.randint(1, 1000000),
                labels=[],
                os="linux",
                name=runner.name,
                status=(
                    GitHubRunnerStatus.OFFLINE
                    if runner.github_state == GitHubRunnerState.OFFLINE
                    else GitHubRunnerStatus.ONLINE
                ),
            )
            for runner in self.state.runners.values()
            if runner.github_state in github_state_set
        )

    def delete_runners(self, states: Iterable[GitHubRunnerState]) -> None:
        """Delete the runners.

        Args:
            states: The states to filter the runners to delete.
        """
        github_states = set(states)
        self.state.runners = {
            instance_id: runner
            for instance_id, runner in self.state.runners.items()
            if runner.github_state not in github_states
        }
