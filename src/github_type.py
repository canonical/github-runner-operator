# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Type of returned data from GitHub web API."""


from __future__ import annotations

from enum import Enum
from typing import TypedDict

from typing_extensions import NotRequired


class GitHubRunnerStatus(Enum):
    """Status of runner on GitHub."""

    online = "online"
    offline = "offline"


class RunnerApplication(TypedDict, total=False):
    """Information on a single runner application."""

    os: str
    architecture: str
    download_url: str
    filename: str
    temp_download_token: NotRequired[str]
    sha256_checksum: NotRequired[str]


RunnerApplicationList = list[RunnerApplication]


class SelfHostedRunnerLabel(TypedDict, total=False):
    """A single label of self-hosted runners."""

    id: NotRequired[int]
    name: str
    type: NotRequired[str]


class SelfHostedRunner(TypedDict):
    """Information on a single self-hosted runner."""

    id: int
    name: str
    os: str
    status: GitHubRunnerStatus
    busy: bool
    labels: list[SelfHostedRunnerLabel]


class SelfHostedRunnerList(TypedDict):
    """Information on a collection of self-hosted runners."""

    total_count: int
    runners: list[SelfHostedRunner]


class RegisterToken(TypedDict):
    """Token used for registering github runners."""

    token: str
