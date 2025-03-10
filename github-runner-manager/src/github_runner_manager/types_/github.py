# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing GitHub API related types."""


from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel


class GitHubRunnerStatus(str, Enum):
    """Status of runner on GitHub.

    Attributes:
        ONLINE: Represents an online runner status.
        OFFLINE: Represents an offline runner status.
    """

    ONLINE = "online"
    OFFLINE = "offline"


# See response schema for
# https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#list-runner-applications-for-an-organization
class RunnerApplication(BaseModel):
    """Information on the runner application.

    Attributes:
        os: Operating system to run the runner application on.
        architecture: Computer Architecture to run the runner application on.
        download_url: URL to download the runner application.
        filename: Filename of the runner application.
    """

    os: Literal["linux", "win", "osx"]
    architecture: Literal["arm", "arm64", "x64"]
    download_url: str
    filename: str


RunnerApplicationList = List[RunnerApplication]


class SelfHostedRunnerLabel(BaseModel):
    """A single label of self-hosted runners.

    Attributes:
        name: Name of the label.
    """

    name: str


class SelfHostedRunner(BaseModel):
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


class SelfHostedRunnerList(BaseModel):
    """Information on a collection of self-hosted runners.

    Attributes:
        total_count: Total number of runners.
        runners: List of runners.
    """

    total_count: int
    runners: list[SelfHostedRunner]


class RegistrationToken(BaseModel):
    """Token used for registering GitHub runners.

    Attributes:
        token: Token for registering GitHub runners.
        expires_at: Time the token expires at.
    """

    token: str
    expires_at: str


class RemoveToken(BaseModel):
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


class JobStatus(str, Enum):
    """Status of a job on GitHub.

    Attributes:
        QUEUED: Represents a job that is queued.
        IN_PROGRESS: Represents a job that is in progress.
        COMPLETED: Represents a job that is completed.
        WAITING: Represents a job that is waiting.
        REQUESTED: Represents a job that is requested.
        PENDING: Represents a job that is pending.
    """

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"
    PENDING = "pending"


class JobInfo(BaseModel):
    """Stats for a job on GitHub.

    Attributes:
        job_id: The ID of the job.
        created_at: The time the job was created.
        started_at: The time the job was started.
        conclusion: The end result of a job.
        status: The status of the job.
    """

    job_id: int
    created_at: datetime
    started_at: datetime
    conclusion: Optional[JobConclusion]
    status: JobStatus
