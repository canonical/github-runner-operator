# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Runner class."""


from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional, TypedDict, Union


@dataclass
class RunnerByHealth:
    """Set of runners LXD instance by health state."""

    healthy: tuple[str]
    unhealthy: tuple[str]


class ProxySetting(TypedDict, total=False):
    """Represent HTTP-related proxy settings."""

    no_proxy: str
    http: str
    https: str


@dataclass
class GithubRepo:
    """Represent GitHub repository."""

    owner: str
    repo: str

    def path(self) -> str:
        """Return a string representing the path."""
        return f"{self.owner}/{self.repo}"


@dataclass
class GithubOrg:
    """Represent GitHub organization."""

    org: str
    group: str

    def path(self) -> str:
        """Return a string representing the path."""
        return self.org


GithubPath = Union[GithubOrg, GithubRepo]


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration."""

    cpu: int
    memory: str
    disk: str


@dataclass
class RunnerConfig:
    """Configuration for runner.

    Attributes:
        name: Name of the runner.
        app_name: Application name of the charm.
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        proxies: HTTP(S) proxy settings.
        lxd_storage_path: Path to be used as LXD storage.
        issue_metrics: Whether to issue metrics.
        dockerhub_mirror: URL of dockerhub mirror to use.
    """

    name: str
    app_name: str
    path: GithubPath
    proxies: ProxySetting
    lxd_storage_path: Path
    issue_metrics: bool
    dockerhub_mirror: str | None = None


@dataclass
class RunnerStatus:
    """Status of runner.

    Attributes:
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_id: Optional[int] = None
    exist: bool = False
    online: bool = False
    busy: bool = False
