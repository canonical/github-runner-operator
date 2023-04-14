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
    """Represents LXD device profile."""

    path: str
    pool: str
    type: str
    size: str


class ResourceProfileDevices(TypedDict):
    """Represents LXD device profile."""

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
