# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Runner class."""


from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TypedDict

from charm_state import GithubPath, SSHDebugInfo


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
    aproxy_address: str


@dataclass
# The instance attributes are all required and is better standalone each.
class RunnerConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration for runner.

    Attributes:
        app_name: Application name of the charm.
        issue_metrics: Whether to issue metrics.
        lxd_storage_path: Path to be used as LXD storage.
        name: Name of the runner.
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        proxies: HTTP(S) proxy settings.
        dockerhub_mirror: URL of dockerhub mirror to use.
        ssh_debug_info: The SSH debug server connection metadata.
    """

    app_name: str
    issue_metrics: bool
    lxd_storage_path: Path
    name: str
    path: GithubPath
    proxies: ProxySetting
    dockerhub_mirror: str | None = None
    ssh_debug_info: SSHDebugInfo | None = None


@dataclass
class RunnerStatus:
    """Status of runner.

    Attributes:
        runner_id: ID of the runner.
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_id: Optional[int] = None
    exist: bool = False
    online: bool = False
    busy: bool = False
