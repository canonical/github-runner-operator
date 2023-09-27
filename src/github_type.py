# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Return type for the GitHub web API."""


from __future__ import annotations

from enum import Enum
from typing import List, TypedDict

from typing_extensions import NotRequired


class GitHubRunnerStatus(Enum):
    """Status of runner on GitHub."""

    ONLINE = "online"
    OFFLINE = "offline"


class RunnerApplication(TypedDict, total=False):
    """Information on the runner application.

    Attrs:
        os: Operating system to run the runner application on.
        architecture: Computer Architecture to run the runner application on.
        download_url: URL to download the runner application.
        filename: Filename of the runner application.
        temp_download_token: A short lived bearer token used to download the
            runner, if needed.
        sha256_check_sum: SHA256 Checksum of the runner application.
    """

    os: str
    architecture: str
    download_url: str
    filename: str
    temp_download_token: NotRequired[str]
    sha256_checksum: NotRequired[str]


RunnerApplicationList = List[RunnerApplication]


class SelfHostedRunnerLabel(TypedDict, total=False):
    """A single label of self-hosted runners.

    Attrs:
        id: Unique identifier of the label.
        name: Name of the label.
        type: Type of label. Read-only labels are applied automatically when
            the runner is configured.
    """

    id: NotRequired[int]
    name: str
    type: NotRequired[str]


class SelfHostedRunner(TypedDict):
    """Information on a single self-hosted runner.

    Attrs:
        id: Unique identifier of the runner.
        name: Name of the runner.
        os: Operation system of the runner.
        busy: Whether the runner is executing a job.
        labels: Labels of the runner.
    """

    id: int
    name: str
    os: str
    status: GitHubRunnerStatus
    busy: bool
    labels: list[SelfHostedRunnerLabel]


class SelfHostedRunnerList(TypedDict):
    """Information on a collection of self-hosted runners.

    Attrs:
        total_count: Total number of runners.
        runners: List of runners.
    """

    total_count: int
    runners: list[SelfHostedRunner]


class RegistrationToken(TypedDict):
    """Token used for registering GitHub runners.

    Attrs:
        token: Token for registering GitHub runners.
        expires_at: Time the token expires at.
    """

    token: str
    expires_at: str


class RemoveToken(TypedDict):
    """Token used for removing GitHub runners.

    Attrs:
        token: Token for removing GitHub runners.
        expires_at: Time the token expires at.
    """

    token: str
    expires_at: str
