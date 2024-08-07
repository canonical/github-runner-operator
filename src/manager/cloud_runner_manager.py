# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface of manager of runner instance on clouds."""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

InstanceId = str


class CloudRunnerState(str, Enum):
    """Represent state of the instance hosting the runner."""

    CREATED = "created"
    ACTIVE = "active"
    DELETED = "deleted"
    ERROR = "error"
    STOPPED = "stopped"
    UNKNOWN = "unknown"
    UNEXPECTED = "unexpected"

    @staticmethod
    def from_openstack_server_status(openstack_server_status: str) -> None:
        """Create from openstack server status.

        The openstack server status are documented here:
        https://docs.openstack.org/api-guide/compute/server_concepts.html

        Args:
            openstack_server_status: Openstack server status.
        """
        match openstack_server_status:
            case "BUILD":
                return CloudRunnerState.CREATED
            case "REBUILD":
                return CloudRunnerState.CREATED
            case "ACTIVE":
                return CloudRunnerState.ACTIVE
            case "ERROR":
                return CloudRunnerState.ERROR
            case "STOPPED":
                return CloudRunnerState.STOPPED
            case "DELETED":
                return CloudRunnerState.DELETED
            case "UNKNOWN":
                return CloudRunnerState.UNKNOWN
            case _:
                return CloudRunnerState.UNEXPECTED


@dataclass
class CloudRunnerInstance:
    """Information on the runner on the cloud.

    Attributes:
        name: Name of the instance hosting the runner.
        id: ID of the instance.
        state: State of the instance hosting the runner.
    """

    name: str
    id: str
    state: CloudRunnerState


class CloudRunnerManager(ABC):
    """Manage runner instance on cloud."""

    def get_name_prefix(self) -> str:
        """Get the name prefix of the self-hosted runners.

        Returns:
            The name prefix.
        """
        ...

    def create_runner(self, registration_token: str) -> InstanceId:
        """Create a self-hosted runner.

        Args:
            registration_token: The GitHub registration token for registering runners.

        Returns:
            Instance ID of the runner.
        """
        ...

    def get_runner(self, id: InstanceId) -> CloudRunnerInstance:
        """Get a self-hosted runner by instance id.

        Args:
            id: The instance id.

        Returns:
            Information on the runner instance.
        """
        ...

    def get_runners(self, states: Sequence[CloudRunnerState]) -> Tuple[CloudRunnerInstance]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.

        Returns:
            Information on the runner instances.
        """
        ...

    def delete_runner(self, id: InstanceId, remove_token: str) -> None:
        """Delete self-hosted runners.

        Args:
            id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.
        """
        ...

    def cleanup_runner(self, remove_token: str) -> None:
        """Cleanup runner and resource on the cloud.

        Args:
            remove_token: The GitHub remove token.
        """
        ...
