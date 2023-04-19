# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Lxd class."""

from __future__ import annotations

from typing import TypedDict

# The keys are not valid identifiers, hence this is defined with function-based syntax.
ResourceProfileConfig = TypedDict(
    "ResourceProfileConfig", {"limits.cpu": str, "limits.memory": str}
)
ResourceProfileConfig.__doc__ = "Represent LXD profile configuration."


class ResourceProfileDevicesRoot(TypedDict):
    """Represents LXD device profile of disk used as root.

    The details of the configuration of different types of devices can be found here:
    https://linuxcontainers.org/lxd/docs/latest/reference/devices/

    For example, configuration for disk:
    https://linuxcontainers.org/lxd/docs/latest/reference/devices_disk/#

    The unit of storage and network limits can be found here:
    https://linuxcontainers.org/lxd/docs/latest/reference/instance_units/#instances-limit-units
    """

    path: str
    pool: str
    type: str
    size: str


class ResourceProfileDevices(TypedDict):
    """Represents LXD device profile for a LXD instance.

    A device for root is defined.

    The details of the configuration can be found in this link:
    https://linuxcontainers.org/lxd/docs/latest/reference/devices/
    """

    root: ResourceProfileDevicesRoot


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
