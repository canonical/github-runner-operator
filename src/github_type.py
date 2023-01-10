# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Type of returned data from GitHub web API."""


from dataclasses import dataclass
from typing import List, TypedDict


class RunnerApplication(TypedDict, total=False):
    """Information on a single runner application."""

    os: str
    architecture: str
    download_url: str
    filename: str
    sha256_checksum: str  # NotRequired


RunnerApplicationList = List[RunnerApplication]


class SelfHostedRunnerLabel(TypedDict, total=False):
    """A single label of self-hosted runners."""

    id: int  # NotRequired
    name: str
    type: str  # NotRequired


class SelfHostedRunner(TypedDict):
    """Information on a single self-hosted runner."""

    id: int
    name: str
    os: str
    status: str
    busy: bool
    labels: List[SelfHostedRunnerLabel]


class SelfHostedRunnerList(TypedDict):
    """Information on a collection of self-hosted runners."""

    total_count: int
    runners: List[SelfHostedRunner]
