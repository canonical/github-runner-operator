# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by RunnerManager class."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Iterable

import jinja2
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient

from charm_state import CharmState, GitHubPath, ReactiveConfig
from github_client import GithubClient
from github_type import GitHubRunnerStatus
from lxd import LxdClient


class LXDFlushMode(Enum):
    """Strategy for flushing runners.

    During pre-job (repo-check), the runners are marked as idle and if the pre-job fails, the
    runner falls back to being idle again. Hence wait_repo_check is required.

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
        repo: Used to interact with repo-policy-compliance API.
    """

    github: GithubClient
    jinja: jinja2.Environment
    lxd: LxdClient
    repo: RepoPolicyComplianceClient


@dataclass
# The instance attributes are all required.
class LXDRunnerManagerConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration of runner manager.

    Attributes:
        are_metrics_enabled: Whether metrics for the runners should be collected.
        charm_state: The state of the charm.
        image: Name of the image for creating LXD instance.
        lxd_storage_path: Path to be used as LXD storage.
        path: GitHub repository path in the format '<owner>/<repo>', or the
            GitHub organization name.
        service_token: Token for accessing local service.
        token: GitHub personal access token to register runner to the
            repository or organization.
        dockerhub_mirror: URL of dockerhub mirror to use.
        reactive_config: The configuration to spawn runners reactively.
    """

    charm_state: CharmState
    image: str
    lxd_storage_path: Path
    path: GitHubPath
    service_token: str
    token: str
    dockerhub_mirror: str | None = None
    reactive_config: ReactiveConfig | None = None

    @property
    def are_metrics_enabled(self) -> bool:
        """Whether metrics for the runners should be collected."""
        return self.charm_state.is_metrics_logging_available


# This class is subject to refactor.
@dataclass
class OpenstackRunnerManagerConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration of runner manager.

    Attributes:
        charm_state: The state of the charm.
        path: GitHub repository path in the format '<owner>/<repo>', or the
            GitHub organization name.
        labels: Additional labels for the runners.
        token: GitHub personal access token to register runner to the
            repository or organization.
        flavor: OpenStack flavor for defining the runner resources.
        image: Openstack image id to boot the runner with.
        network: OpenStack network for runner network access.
        dockerhub_mirror: URL of dockerhub mirror to use.
        reactive_config: The configuration to spawn runners reactively.
    """

    charm_state: CharmState
    path: GitHubPath
    labels: Iterable[str]
    token: str
    flavor: str
    image: str
    network: str
    dockerhub_mirror: str | None
    reactive_config: ReactiveConfig | None = None


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
