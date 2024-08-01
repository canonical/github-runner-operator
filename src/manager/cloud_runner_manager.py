# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

RunnerId = str

_OPENSTACK_STATUS_SHUTOFF = "SHUTOFF"
_OPENSTACK_STATUS_ERROR = "ERROR"
_OPENSTACK_STATUS_ACTIVE = "ACTIVE"
_OPENSTACK_STATUS_BUILDING = "BUILDING"

class CloudRunnerStatus(str, Enum):
    created = "created"
    active = "active"
    deleted = "deleted"
    error = "error"
    stopped = "stopped"
    unknown = "unknown"
    unexpected = "unexpected"

    
    def from_openstack_status(status: str) -> "CloudRunnerStatus":
        """Create from openstack server status.
        
        The openstack server status are documented here:
        https://docs.openstack.org/api-guide/compute/server_concepts.html
        
        Args:
            status: Openstack server status.
        
        Returns:
            The CloudRunnerStatus.
        """
        match status:
            case "BUILD":
                return CloudRunnerStatus.created
            case "REBUILD":
                return CloudRunnerStatus.created
            case "ACTIVE":
                return CloudRunnerStatus.active
            case "ERROR":
                return CloudRunnerStatus.error
            case "STOPPED":
                return CloudRunnerStatus.stopped
            case "DELETED":
                return CloudRunnerStatus.deleted
            case "UNKNOWN":
                return CloudRunnerStatus.unknown
            case _:
                return CloudRunnerStatus.unexpected

@dataclass
class RunnerInstance:
    name: str
    id: str
    status: CloudRunnerStatus

@dataclass
class RunnerMetrics:
    pass

class CloudRunnerManager(ABC):
    def create_runner(self, registration_token: str) -> RunnerId: ...

    def get_runner(self, id: RunnerId) -> RunnerInstance: ...

    def get_runners(
        self, cloud_runner_status: list[CloudRunnerStatus]
    ) -> Tuple[RunnerInstance]: ...

    def delete_runners(self, id: RunnerId, remove_token: str) -> None: ...
