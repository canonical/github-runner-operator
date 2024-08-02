# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

RunnerId = str

_OPENSTACK_STATUS_SHUTOFF = "SHUTOFF"
_OPENSTACK_STATUS_ERROR = "ERROR"
_OPENSTACK_STATUS_ACTIVE = "ACTIVE"
_OPENSTACK_STATUS_BUILDING = "BUILDING"


class CloudRunnerState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    DELETED = "deleted"
    ERROR = "error"
    STOPPED = "stopped"
    UNKNOWN = "unknown"
    UNEXPECTED = "unexpected"

    def __init__(openstack_server_status: str) -> None:
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
    status: CloudRunnerState


@dataclass
class RunnerMetrics:
    pass


class CloudRunnerManager(ABC):
    def create_runner(self, registration_token: str) -> RunnerId: ...

    def get_runner(self, id: RunnerId) -> CloudRunnerInstance: ...

    def get_runners(
        self, cloud_runner_status: Sequence[CloudRunnerState]
    ) -> Tuple[CloudRunnerInstance]: ...

    def delete_runner(self, id: RunnerId, remove_token: str) -> None: ...

    def cleanup_runner(self, remove_token: str) -> None: ...
