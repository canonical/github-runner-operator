# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Lxd class.

The details of the configuration of different types of devices can be found here:
https://linuxcontainers.org/lxd/docs/latest/reference/devices/

For example, configuration for disk:
https://linuxcontainers.org/lxd/docs/latest/reference/devices_disk/#

The unit of storage and network limits can be found here:
https://linuxcontainers.org/lxd/docs/latest/reference/instance_units/#instances-limit-units
"""

from dataclasses import dataclass
from typing import TypedDict

# The keys are not valid identifiers, hence this is defined with function-based syntax.
LxdResourceProfileConfig = TypedDict(
    "LxdResourceProfileConfig", {"limits.cpu": str, "limits.memory": str}
)
LxdResourceProfileConfig.__doc__ = "Configuration LXD profile."


# The keys are not valid identifiers, hence this is defined with function-based syntax.
LxdResourceProfileDevicesDisk = TypedDict(
    "LxdResourceProfileDevicesDisk",
    {"path": str, "pool": str, "type": str, "size": str, "io.cache": str},
)
LxdResourceProfileDevicesDisk.__doc__ = "LXD device profile of disk."


LxdResourceProfileDevices = dict[str, LxdResourceProfileDevicesDisk]


class LxdInstanceConfigSource(TypedDict):
    """Configuration for source image in the LXD instance.

    Attributes:
        type: Type of source configuration, e.g. image, disk
        server: The source server URL, e.g. https://cloud-images.ubuntu.com/releases
        protocol: Protocol of the configuration, e.g. simplestreams
        alias: Alias for configuration.
    """

    type: str
    server: str
    protocol: str
    alias: str


class LxdInstanceConfig(TypedDict):
    """Configuration for the LXD instance.

    See https://documentation.ubuntu.com/lxd/en/latest/howto/instances_create/

    Attributes:
        name: Name of the instance.
        type: Instance type, i.e. "container" or "virtual-machine".
        source: Instance creation source configuration.
        ephemeral: Whether the container should be deleted after a single run.
        profiles: List of LXD profiles applied to the instance.
    """

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
    """Configuration of the storage pool.

    Attributes:
        source: The storage pool configuration source image.
        size: The size of the storage pool, e.g. 30GiB
    """

    source: str
    size: str


class LxdStoragePoolConfiguration(TypedDict):
    """Configuration for LXD storage pool.

    Attributes:
        name: The storage pool name.
        driver: The storage driver being used, i.e. "dir", "btrfs", ... . See \
            https://documentation.ubuntu.com/lxd/en/stable-5.0/reference/storage_drivers/ \
            for more information.
        config: The storage pool configuration.
    """

    name: str
    driver: str
    config: LxdStoragePoolConfig


@dataclass
class LxdNetwork:
    """LXD network information.

    Attributes:
        name: The name of LXD network.
        description: LXD network descriptor.
        type: Network type, i.e. "bridge", "physical"
        config: The LXD network configuration values.
        managed: Whether the network is being managed by lxd.
        used_by: Number of instances using the network.
    """

    name: str
    description: str
    type: str
    config: LxdNetworkConfig
    managed: bool
    used_by: tuple[str]
