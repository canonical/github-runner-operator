# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for managing the runners."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

from charm_state import GithubPath
from github_type import SelfHostedRunner
from manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    RunnerId,
)
from manager.github_runner_manager import GithubRunnerManager, GithubRunnerState


class FlushMode(Enum):
    """Strategy for flushing runners.

    Attributes:
        FLUSH_IDLE: Flush idle runners.
        FLUSH_BUSY: Flush busy runners.
    """

    FLUSH_IDLE = auto()
    FLUSH_BUSY = auto()


@dataclass
class RunnerInstance:
    name: str
    id: RunnerId
    github_state: GithubRunnerState
    cloud_state: CloudRunnerState

    def __init__(
        self, cloud_instance: CloudRunnerInstance, github_info: SelfHostedRunner
    ) -> "RunnerInstance":
        self.name = github_info.name
        self.id = cloud_instance.id
        self.github_state = GithubRunnerState(github_info)
        self.cloud_state = cloud_instance.state


@dataclass
class RunnerManagerConfig:
    token: str
    path: GithubPath


class RunnerManager:

    def __init__(self, cloud_runner_manager: CloudRunnerManager, config: RunnerManagerConfig):
        self._config = config
        self._cloud = cloud_runner_manager
        self._github = GithubRunnerManager(
            prefix=self._cloud.get_name_prefix(), token=self._config.token, path=self._config.path
        )

    def create_runners(self, num: int) -> tuple[RunnerId]:
        registration_token = self._github.get_registration_token()

        runner_ids = []
        for _ in range(num):
            runner_ids.append(self._cloud.create_runner(registration_token=registration_token))

        return tuple(runner_ids)

    def get_runners(
        self,
        github_runner_state: Sequence[GithubRunnerState] | None = None,
        cloud_runner_state: Sequence[CloudRunnerState] | None = None,
    ) -> tuple[RunnerInstance]:
        """Get information on runner filter by state.

        Args:
            github_runner_state: Filter for the runners with these github states. If None all
                states will be included.
            cloud_runner_state: Filter for the runners with these cloud states. If None all states
                will be included.

        Returns:
            Information on the runners.
        """
        github_infos = self._github.get_runners(github_runner_state)
        cloud_infos = self._cloud.get_runners(cloud_runner_state)
        github_infos_map = {info.name: info for info in github_infos}
        cloud_infos_map = {info.name: info for info in cloud_infos}
        return tuple(
            RunnerInstance(cloud_infos_map[name], github_infos_map[name])
            for name in cloud_infos_map.keys() & github_infos_map.keys()
        )

    def delete_runners(self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE) -> None:
        states = [GithubRunnerState.IDLE]
        if flush_mode == FlushMode.FLUSH_BUSY:
            states.append(GithubRunnerState.BUSY)

        runners_list = self.get_runners(github_runner_state=states)
        remove_token = self._github.get_removal_token()

        for runner in runners_list:
            self._cloud.delete_runners(id=runner.id, remove_token=remove_token)

    def cleanup(self) -> None:
        self._github.delete_runners([GithubRunnerState.OFFLINE, GithubRunnerState.UNKNOWN])
        remove_token = self._github.get_removal_token()
        self._cloud.cleanup_runner(remove_token)
