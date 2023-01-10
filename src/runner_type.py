# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by both RunnerManager and Runner classes."""


from dataclasses import dataclass
from typing import NamedTuple, TypedDict, Union


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
        return f"{self.owner}/{self.repo}"


@dataclass
class GitHubOrg:
    """Represent GitHub organization."""

    org: str

    def path(self) -> str:
        return self.org


GitHubPath = Union[GitHubOrg, GitHubRepo]


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration."""

    cpu: int
    memory: str
    disk: str
