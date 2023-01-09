# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Type of returned data from GitHub web API."""


from dataclasses import dataclass
from typing import List, TypedDict


@dataclass
class RunnerApplication(TypedDict, total=False):
    os: str
    architecture: str
    download_url: str
    filename: str
    sha256_checksum: str  # NotRequired


RunnerApplicationList = List[RunnerApplication]


@dataclass
class SelfHostedRunnerLabel(TypedDict, total=False):
    id: int  # NotRequired
    name: str
    type: str  # NotRequired


@dataclass
class SelfHostedRunner(TypedDict):
    id: int
    name: str
    os: str
    status: str
    busy: bool
    labels: List[SelfHostedRunnerLabel]


@dataclass
class SelfHostedRunnerList(TypedDict):
    total_count: int
    runners: List[SelfHostedRunner]
