# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by both RunnerManager and Runner classes."""


from dataclasses import dataclass
from typing import NamedTuple, Optional, TypedDict, Union

import jinja2
from ghapi.all import GhApi

from lxd import LxdClient
from repo_policy_compliance_client import RepoPolicyComplianceClient


class ProxySetting(TypedDict, total=False):
    """Represent HTTP-related proxy settings."""

    no_proxy: str
    http: str
    https: str


@dataclass
class GitHubRepo:
    """Represent GitHub repository."""

    owner: str
    repo: str

    def path(self) -> str:
        """Return a string representing the path."""
        return f"{self.owner}/{self.repo}"


@dataclass
class GitHubOrg:
    """Represent GitHub organization."""

    org: str
    group: str

    def path(self) -> str:
        """Return a string representing the path."""
        return self.org


GitHubPath = Union[GitHubOrg, GitHubRepo]


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration."""

    cpu: int
    memory: str
    disk: str


@dataclass
class RunnerClients:
    """Clients for access various services.

    Attrs:
        github: Used to query GitHub API.
        jinja: Used for templating.
        lxd: Used to interact with LXD API.
    """

    github: GhApi
    jinja: jinja2.Environment
    lxd: LxdClient
    repo: RepoPolicyComplianceClient


@dataclass
class RunnerConfig:
    """Configuration for runner."""

    app_name: str
    path: GitHubPath
    proxies: ProxySetting
    lvm_vg_name: str
    name: str


@dataclass
class RunnerStatus:
    """Status of runner.

    Attrs:
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_id: Optional[int] = None
    exist: bool = False
    online: bool = False
    busy: bool = False
