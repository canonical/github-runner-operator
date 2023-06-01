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
    """Represent HTTP-related proxy settings.

    Attrs:
        no_proxy: Comma separated list of domain names to not use HTTP(S) proxy.
        http: HTTP proxy to use.
        https: HTTPS proxy to use.
    """

    no_proxy: str
    http: str
    https: str


@dataclass
class GitHubRepo:
    """Represent GitHub repository.

    Attrs:
        owner: The owner of the GitHub repository.
        repo: The GitHub repository name.
    """

    owner: str
    repo: str

    def path(self) -> str:
        """Path to refer to the GitHub repo.

        Returns:
            The path.
        """
        return f"{self.owner}/{self.repo}"


@dataclass
class GitHubOrg:
    """Represent GitHub organization.

    Attrs:
        org: The GitHub organization owning the GitHub repository.
        group: The runner group.
    """

    org: str
    group: str

    def path(self) -> str:
        """Path to refer to the GitHub organization.

        Returns:
            The path.
        """
        return self.org


GitHubPath = Union[GitHubOrg, GitHubRepo]


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration.

    Attrs:
        cpu: Max number of vCPU to use.
        memory: Max memory to use.
        disk: Max disk space to use.
        disk_read: Max disk read speed.
        disk_write: Max disk write speed.
    """

    cpu: int
    memory: str
    disk: str
    disk_read: str
    disk_write: str


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
    """Configuration for runner.

    Attrs:
        app_name: Application name of the charm
        path: Path to refer to the GitHub repo or GitHub org.
        proxies: HTTP(S) Proxy settings.
        name: Name of the runner.
    """

    app_name: str
    path: GitHubPath
    proxies: ProxySetting
    name: str


@dataclass
class RunnerStatus:
    """Status of runner.

    Attrs:
        runner_id: The id assigned by GitHub to the runner upon connecting to GitHub.
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_id: Optional[int] = None
    exist: bool = False
    online: bool = False
    busy: bool = False
