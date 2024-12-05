# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manage the lifecycle of runners.

The `Runner` class stores the information on the runners and manages the
lifecycle of the runners on LXD and GitHub.

The `RunnerManager` class from `runner_manager.py` creates and manages a
collection of `Runner` instances.
"""

import logging
import pathlib
from dataclasses import dataclass
from pathlib import Path

from charm_state import Arch, VirtualMachineResources

logger = logging.getLogger(__name__)
LXD_PROFILE_YAML = pathlib.Path(__file__).parent.parent / "lxd-profile.yaml"
if not LXD_PROFILE_YAML.exists():
    LXD_PROFILE_YAML = LXD_PROFILE_YAML.parent / "lxd-profile.yml"
LXDBR_DNSMASQ_LEASES_FILE = Path("/var/snap/lxd/common/lxd/networks/lxdbr0/dnsmasq.leases")

APROXY_ARM_REVISION = 9
APROXY_AMD_REVISION = 8

METRICS_EXCHANGE_PATH = Path("/metrics-exchange")
DIAG_DIR_PATH = Path("/home/ubuntu/github-runner/_diag")


@dataclass
class WgetExecutable:
    """The executable to be installed through wget.

    Attributes:
        url: The URL of the executable binary.
        cmd: Executable command name. E.g. yq_linux_amd64 -> yq
    """

    url: str
    cmd: str


@dataclass
class CreateRunnerConfig:
    """The configuration values for creating a single runner instance.

    Attributes:
        image: Name of the image to launch the LXD instance with.
        resources: Resource setting for the LXD instance.
        binary_path: Path to the runner binary.
        registration_token: Token for registering the runner on GitHub.
        arch: Current machine architecture.
    """

    image: str
    resources: VirtualMachineResources
    binary_path: Path
    registration_token: str
    arch: Arch = Arch.X64
