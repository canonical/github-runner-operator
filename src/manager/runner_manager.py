# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for managing the GitHub self-hosted runners hosted on cloud instances."""

import logging
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

logger = logging.getLogger(__name__)


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
    """Represents an instance of runner.

    Attributes:
        name: Full name of the runner. Managed by the cloud runner manager.
        id: ID of the runner. Managed by the runner manager.
        github_state: State on github.
        cloud_state: State on cloud.
    """

    name: str
    id: RunnerId
    github_state: GithubRunnerState
    cloud_state: CloudRunnerState

    def __init__(
        self, cloud_instance: CloudRunnerInstance, github_info: SelfHostedRunner
    ) -> "RunnerInstance":
        """Construct an instance.

        Args:
            cloud_instance: Information on the cloud instance.
            github_info: Information on the GitHub of the runner.
        Returns:
            A RunnerInstance object.
        """
        self.name = github_info.name
        self.id = cloud_instance.id
        self.github_state = GithubRunnerState.from_runner(github_info)
        self.cloud_state = cloud_instance.state


@dataclass
class RunnerManagerConfig:
    """Configuration for the runner manager.

    Attributes:
        token: GitHub personal access token to query GitHub API.
        path: Path to GitHub repository or organization to registry the runners.
    """

    token: str
    path: GithubPath


class RunnerManager:
    """Manage the runners."""

    def __init__(self, cloud_runner_manager: CloudRunnerManager, config: RunnerManagerConfig):
        """Construct the object.

        Args:
            cloud_runner_manager: For managing the cloud instance of the runner.
            config: Configuration of this class.
        """
        self._config = config
        self._cloud = cloud_runner_manager
        self._github = GithubRunnerManager(
            prefix=self._cloud.get_name_prefix(), token=self._config.token, path=self._config.path
        )

    def create_runners(self, num: int) -> tuple[RunnerId]:
        """Create runners.

        Args:
            num: Number of runners to create.

        Returns:
            List of instance ID of the runners.
        """
        logger.info("Creating %s runners", num)
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
        logger.info("Getting runners...")
        github_infos = self._github.get_runners(github_runner_state)
        cloud_infos = self._cloud.get_runners(cloud_runner_state)
        github_infos_map = {info.name: info for info in github_infos}
        cloud_infos_map = {info.name: info for info in cloud_infos}
        runner_names = cloud_infos_map.keys() & github_infos_map.keys()
        logger.info("Found following runners: %s", runner_names)

        cloud_only = cloud_infos_map.keys() - runner_names
        github_only = github_infos_map.keys() - runner_names
        if cloud_only:
            logger.warning(
                "Found runner instance on cloud but not registered on GitHub: %s", cloud_only
            )
        if github_only:
            logger.warning(
                "Found self-hosted runner on GitHub but no matching runner instance on cloud: %s",
                github_only,
            )

        return tuple(
            RunnerInstance(cloud_infos_map[name], github_infos_map[name]) for name in runner_names
        )

    def delete_runners(self, flush_mode: FlushMode = FlushMode.FLUSH_IDLE) -> None:
        """Delete the runners.

        Args:
            flush_mode: The type of runners affect by the deletion.
        """
        match flush_mode:
            case FlushMode.FLUSH_IDLE:
                logger.info("Deleting idle runners...")
            case FlushMode.FLUSH_BUSY:
                logger.info("Deleting idle and busy runners...")
            case _:
                logger.critical(
                    "Unknown flush mode %s encountered, contact developers", flush_mode
                )

        states = [GithubRunnerState.IDLE]
        if flush_mode == FlushMode.FLUSH_BUSY:
            states.append(GithubRunnerState.BUSY)

        runners_list = self.get_runners(github_runner_state=states)
        runner_names = [runner.name for runner in runners_list]
        logger.info("Deleting runners: %s", runner_names)
        remove_token = self._github.get_removal_token()

        for runner in runners_list:
            self._cloud.delete_runner(id=runner.id, remove_token=remove_token)

    def cleanup(self) -> None:
        """Run cleanup of the runners and other resources."""
        self._github.delete_runners([GithubRunnerState.OFFLINE, GithubRunnerState.UNKNOWN])
        remove_token = self._github.get_removal_token()
        self._cloud.cleanup_runner(remove_token)
