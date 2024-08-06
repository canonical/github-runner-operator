# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

RunnerId = str


class CloudRunnerState(str, Enum):
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
            status: Openstack server status.
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
    name: str
    id: str
    state: CloudRunnerState


@dataclass
class RunnerMetrics:
    pass


class CloudRunnerManager(ABC):
    def get_name_prefix(self) -> str: ...

    def create_runner(self, registration_token: str) -> RunnerId: ...

    def get_runner(self, id: RunnerId) -> CloudRunnerInstance: ...

    def get_runners(self, states: Sequence[CloudRunnerState]) -> Tuple[CloudRunnerInstance]: ...

    def delete_runner(self, id: RunnerId, remove_token: str) -> None: ...

    def cleanup_runner(self, remove_token: str) -> None: ...
