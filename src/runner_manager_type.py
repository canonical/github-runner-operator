# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by RunnerManager class."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import jinja2

from charm_state import CharmState, GithubPath
from github_client import GithubClient
from github_type import GitHubRunnerStatus
from lxd import LxdClient
from repo_policy_compliance_client import RepoPolicyComplianceClient


class FlushMode(Enum):
    """Strategy for flushing runners.

    Attributes:
        FLUSH_IDLE: Flush only idle runners.
        FLUSH_IDLE_WAIT_REPO_CHECK: Flush only idle runners, then wait until repo-policy-check is
            completed for the busy runners.
        FLUSH_BUSY: Flush busy runners.
        FLUSH_BUSY_WAIT_REPO_CHECK: Wait until the repo-policy-check is completed before
            flush of busy runners.
        FORCE_FLUSH_WAIT_REPO_CHECK: Force flush the runners (remove lxd instances even on
            gh api issues, like invalid token).
            Wait until repo-policy-check is completed before force flush of busy runners.
    """

    FLUSH_IDLE = auto()
    FLUSH_IDLE_WAIT_REPO_CHECK = auto()
    FLUSH_BUSY = auto()
    FLUSH_BUSY_WAIT_REPO_CHECK = auto()
    FORCE_FLUSH_WAIT_REPO_CHECK = auto()


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
# The instance attributes are all required.
class RunnerManagerConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration of runner manager.

    Attributes:
        charm_state: The state of the charm.
        image: Name of the image for creating LXD instance.
        lxd_storage_path: Path to be used as LXD storage.
        path: GitHub repository path in the format '<owner>/<repo>', or the
            GitHub organization name.
        service_token: Token for accessing local service.
        token: GitHub personal access token to register runner to the
            repository or organization.
        dockerhub_mirror: URL of dockerhub mirror to use.
    """

    charm_state: CharmState
    image: str
    lxd_storage_path: Path
    path: GithubPath
    service_token: str
    token: str
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
