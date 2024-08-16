# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface of manager of runner instance on clouds."""

import abc
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Sequence, Tuple

from charm_state import GithubPath, ProxyConfig, SSHDebugConnection
from metrics.runner import RunnerMetrics

logger = logging.getLogger(__name__)

InstanceId = str


class HealthState(Enum):
    """Health state of the runners.

    Attributes:
        HEALTHY: The runner is healthy.
        UNHEALTHY: The runner is not healthy.
        UNKNOWN: Unable to get the health state.
    """

    HEALTHY = auto()
    UNHEALTHY = auto()
    UNKNOWN = auto()


class CloudRunnerState(str, Enum):
    """Represent state of the instance hosting the runner.

    Attributes:
        CREATED: The instance is created.
        ACTIVE: The instance is active and running.
        DELETED: The instance is deleted.
        ERROR: The instance has encountered error and not running.
        STOPPED: The instance has stopped.
        UNKNOWN: The state of the instance is not known.
        UNEXPECTED: An unknown state not accounted by the developer is encountered.
    """

    CREATED = auto()
    ACTIVE = auto()
    DELETED = auto()
    ERROR = auto()
    STOPPED = auto()
    UNKNOWN = auto()
    UNEXPECTED = auto()

    @staticmethod
    def from_openstack_server_status(
        openstack_server_status: str,
    ) -> "CloudRunnerState":
        """Create from openstack server status.

        The openstack server status are documented here:
        https://docs.openstack.org/api-guide/compute/server_concepts.html

        Args:
            openstack_server_status: Openstack server status.

        Returns:
            The state of the runner.
        """
        state = CloudRunnerState.UNEXPECTED
        match openstack_server_status:
            case "BUILD":
                state = CloudRunnerState.CREATED
            case "REBUILD":
                state = CloudRunnerState.CREATED
            case "ACTIVE":
                state = CloudRunnerState.ACTIVE
            case "ERROR":
                state = CloudRunnerState.ERROR
            case "STOPPED":
                state = CloudRunnerState.STOPPED
            case "DELETED":
                state = CloudRunnerState.DELETED
            case "UNKNOWN":
                state = CloudRunnerState.UNKNOWN
            case _:
                state = CloudRunnerState.UNEXPECTED
        return state


@dataclass
class GitHubRunnerConfig:
    """Configuration for GitHub runner spawned.

    Attributes:
        github_path: The GitHub organization or repository for runners to connect to.
        labels: The labels to add to runners.
    """

    github_path: GithubPath
    labels: list[str]


@dataclass
class SupportServiceConfig:
    """Configuration for supporting services for runners.

    Attributes:
        proxy_config: The proxy configuration.
        dockerhub_mirror: The dockerhub mirror to use for runners.
        ssh_debug_connections: The information on the ssh debug services.
        repo_policy_url: The URL of the repo policy service.
        repo_policy_token: The token to access the repo policy service.
    """

    proxy_config: ProxyConfig | None
    dockerhub_mirror: str | None
    ssh_debug_connections: list[SSHDebugConnection] | None
    repo_policy_url: str | None
    repo_policy_token: str | None


@dataclass
class CloudRunnerInstance:
    """Information on the runner on the cloud.

    Attributes:
        name: Name of the instance hosting the runner.
        instance_id: ID of the instance.
        health: Health state of the runner.
        state: State of the instance hosting the runner.
    """

    name: str
    instance_id: InstanceId
    health: HealthState
    state: CloudRunnerState


class CloudRunnerManager(abc.ABC):
    """Manage runner instance on cloud.

    Attributes:
        name_prefix: The name prefix of the self-hosted runners.
    """

    @property
    @abc.abstractmethod
    def name_prefix(self) -> str:
        """Get the name prefix of the self-hosted runners."""

    @abc.abstractmethod
    def create_runner(self, registration_token: str) -> InstanceId:
        """Create a self-hosted runner.

        Args:
            registration_token: The GitHub registration token for registering runners.
        """

    @abc.abstractmethod
    def get_runner(self, instance_id: InstanceId) -> CloudRunnerInstance:
        """Get a self-hosted runner by instance id.

        Args:
            instance_id: The instance id.
        """

    @abc.abstractmethod
    def get_runners(self, states: Sequence[CloudRunnerState]) -> Tuple[CloudRunnerInstance]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.
        """

    @abc.abstractmethod
    def delete_runner(self, instance_id: InstanceId, remove_token: str) -> RunnerMetrics | None:
        """Delete self-hosted runners.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.
        """

    @abc.abstractmethod
    def cleanup(self, remove_token: str) -> Iterator[RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Perform health check on runner and delete the runner if it fails.

        Args:
            remove_token: The GitHub remove token.
        """
