from __future__ import annotations

from typing import TypedDict


class LxdException(Exception):
    pass


# The keys are not valid identifiers, hence this is defined with function-based syntax.
ResourceProfileConfig = TypedDict(
    "ResourceProfileCOnfig", {"limits.cpu": str, "limits.memory": str}
)


class ResourceProfileDevicesRoot(TypedDict):
    path: str
    pool: str
    type: str
    size: str


class ResourceProfileDevices(TypedDict):
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
