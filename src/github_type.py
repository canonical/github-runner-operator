# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Return type for the GitHub web API."""


from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, TypedDict

from pydantic import BaseModel
from typing_extensions import NotRequired


class GitHubRunnerStatus(Enum):
    """Status of runner on GitHub.

    Attributes:
        ONLINE: Represents an online runner status.
        OFFLINE: Represents an offline runner status.
    """

    ONLINE = "online"
    OFFLINE = "offline"


# See response schema for
# https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#list-runner-applications-for-an-organization
class RunnerApplication(TypedDict, total=False):
    """Information on the runner application.

    Attributes:
        os: Operating system to run the runner application on.
        architecture: Computer Architecture to run the runner application on.
        download_url: URL to download the runner application.
        filename: Filename of the runner application.
        temp_download_token: A short lived bearer token used to download the
            runner, if needed.
        sha256_checksum: SHA256 Checksum of the runner application.
    """

    os: Literal["linux", "win", "osx"]
    architecture: Literal["arm", "arm64", "x64"]
    download_url: str
    filename: str
    # flake8-docstrings-complete thinks these attributes should not be described in the docstring.
    temp_download_token: NotRequired[str]  # noqa: DCO063
    sha256_checksum: NotRequired[str]  # noqa: DCO063


RunnerApplicationList = List[RunnerApplication]


class SelfHostedRunnerLabel(TypedDict, total=False):
    """A single label of self-hosted runners.

    Attributes:
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

    Attributes:
        busy: Whether the runner is executing a job.
        id: Unique identifier of the runner.
        labels: Labels of the runner.
        os: Operation system of the runner.
        name: Name of the runner.
        status: The Github runner status.
    """

    busy: bool
    id: int
    labels: list[SelfHostedRunnerLabel]
    os: str
    name: str
    status: GitHubRunnerStatus


class SelfHostedRunnerList(TypedDict):
    """Information on a collection of self-hosted runners.

    Attributes:
        total_count: Total number of runners.
        runners: List of runners.
    """

    total_count: int
    runners: list[SelfHostedRunner]


class RegistrationToken(TypedDict):
    """Token used for registering GitHub runners.

    Attributes:
        token: Token for registering GitHub runners.
        expires_at: Time the token expires at.
    """

    token: str
    expires_at: str


class RemoveToken(TypedDict):
    """Token used for removing GitHub runners.

    Attributes:
        token: Token for removing GitHub runners.
        expires_at: Time the token expires at.
    """

    token: str
    expires_at: str


class JobConclusion(str, Enum):
    """Conclusion of a job on GitHub.

    See :https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28\
#list-workflow-runs-for-a-repository

    Attributes:
        ACTION_REQUIRED: Represents additional action required on the job.
        CANCELLED: Represents a cancelled job status.
        FAILURE: Represents a failed job status.
        NEUTRAL: Represents a job status that can optionally succeed or fail.
        SKIPPED: Represents a skipped job status.
        SUCCESS: Represents a successful job status.
        TIMED_OUT: Represents a job that has timed out.
    """

    ACTION_REQUIRED = "action_required"
    CANCELLED = "cancelled"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    SKIPPED = "skipped"
    SUCCESS = "success"
    TIMED_OUT = "timed_out"


class JobStats(BaseModel):
    """Stats for a job on GitHub.

    Attributes:
        created_at: The time the job was created.
        started_at: The time the job was started.
        conclusion: The end result of a job.
    """

    created_at: datetime
    started_at: datetime
    conclusion: Optional[JobConclusion]
