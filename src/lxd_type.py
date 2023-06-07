# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Lxd class.

The details of the configuration of different types of devices can be found here:
https://linuxcontainers.org/lxd/docs/latest/reference/devices/

For example, configuration for disk:
https://linuxcontainers.org/lxd/docs/latest/reference/devices_disk/#

The unit of storage and network limits can be found here:
https://linuxcontainers.org/lxd/docs/latest/reference/instance_units/#instances-limit-units
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

# The keys are not valid identifiers, hence this is defined with function-based syntax.
LxdResourceProfileConfig = TypedDict(
    "LxdResourceProfileConfig", {"limits.cpu": str, "limits.memory": str}
)
LxdResourceProfileConfig.__doc__ = "Configuration LXD profile."


class LxdResourceProfileDevicesDisk(TypedDict):
    """LXD device profile of disk."""

    path: str
    pool: str
    type: str
    size: str


LxdResourceProfileDevices = dict[str, LxdResourceProfileDevicesDisk]


class LxdInstanceConfigSource(TypedDict):
    """Configuration for source image in LXD instance."""

    type: str
    mode: str
    server: str
    protocol: str
    alias: str


class LxdInstanceConfig(TypedDict):
    """Configuration for LXD instance."""

    name: str
    type: str
    source: LxdInstanceConfigSource
    ephemeral: bool
    profiles: list[str]


# The keys are not valid identifiers, hence this is defined with function-based syntax.
LxdNetworkConfig = TypedDict(
    "LxdNetworkConfig",
    {"ipv4.address": str, "ipv4.nat": str, "ipv6.address": str, "ipv6.nat": str},
)
LxdNetworkConfig.__doc__ = "Represent LXD network configuration."


class LxdStoragePoolConfig(TypedDict):
    """Configuration of the storage pool."""

    source: str
    size: str


class LxdStoragePoolConfiguration(TypedDict):
    """Configuration for LXD storage pool."""

    name: str
    driver: str
    config: LxdStoragePoolConfig


@dataclass
class LxdNetwork:
    """LXD network information."""

    name: str
    description: str
    type: str
    config: LxdNetworkConfig
    managed: bool
    used_by: tuple[str]
