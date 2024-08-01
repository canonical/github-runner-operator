# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from dataclasses import dataclass
from enum import Enum

from manager.cloud_runner_manager import CloudRunnerStatus, RunnerId


class GithubRunnerStatus(str, Enum):
    busy = "busy"
    idle = "idle"
    offline = "offline"

@dataclass
class RunnerInstance:
    github_name: str
    id: RunnerId
    github_status: GithubRunnerStatus
    cloud_status: CloudRunnerStatus