# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by RunnerManager class."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import jinja2

from charm_state import State as CharmState
from github_client import GithubClient
from github_type import GitHubRunnerStatus
from lxd import LxdClient
from repo_policy_compliance_client import RepoPolicyComplianceClient
from runner_type import GithubPath


class FlushMode(Enum):
    """Strategy for flushing runners."""

    FLUSH_IDLE = 0
    """Flush only idle runners."""
    FORCE_FLUSH_BUSY = 1
    """Force flush busy runners."""
    FORCE_FLUSH_BUSY_WAIT_REPO_CHECK = 2
    """Wait until the repo-policy-check is completed then force flush busy runners."""


@dataclass
class RunnerManagerClients:
    """Clients for accessing various services.

    Attributes:
        github: Used to query GitHub API.
        jinja: Used for templating.
        lxd: Used to interact with LXD API.
    """

    github: GithubClient
    jinja: jinja2.Environment
    lxd: LxdClient
    repo: RepoPolicyComplianceClient


@dataclass
class RunnerManagerConfig:
    """Configuration of runner manager.

    Attributes:
        path: GitHub repository path in the format '<owner>/<repo>', or the
            GitHub organization name.
        token: GitHub personal access token to register runner to the
            repository or organization.
        image: Name of the image for creating LXD instance.
        service_token: Token for accessing local service.
        lxd_storage_path: Path to be used as LXD storage.
        charm_state: The state of the charm.
        dockerhub_mirror: URL of dockerhub mirror to use.
    """

    path: GithubPath
    token: str
    image: str
    service_token: str
    lxd_storage_path: Path
    charm_state: CharmState
    dockerhub_mirror: str | None = None

    @property
    def are_metrics_enabled(self) -> bool:
        """Whether metrics for the runners should be collected."""
        return self.charm_state.is_metrics_logging_available


@dataclass
class RunnerInfo:
    """Information from GitHub of a runner.

    Used as a returned type to method querying runner information.

    Attributes:
        name: Name of the runner.
        status: Status of the runner.
        busy: Whether the runner has taken a job.
    """

    name: str
    status: GitHubRunnerStatus
    busy: bool
