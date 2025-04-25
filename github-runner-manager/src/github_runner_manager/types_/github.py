# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing GitHub API related types."""


from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, TypedDict

from pydantic import BaseModel

from github_runner_manager.manager.models import InstanceID, RunnerMetadata


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
        status: The Github runner status.
        instance_id: InstanceID of the runner.
        metadata: Runner metadata.
        deletable: Deletable runner. In GitHub, this is equivalent as the runner not
            existing in GitHub, as that runner cannot get jobs.
    """

    busy: bool
    id: int
    labels: list[SelfHostedRunnerLabel]
    status: GitHubRunnerStatus
    instance_id: InstanceID
    metadata: RunnerMetadata
    deletable: bool = False

    @classmethod
    def build_from_github(cls, github_dict: dict, instance_id: InstanceID) -> "SelfHostedRunner":
        """Build a SelfHostedRunner from the GitHub runner information and the InstanceID.

        Args:
            github_dict: GitHub dictionary from the list_runners endpoint.
            instance_id: InstanceID for the runner.

        Returns:
            A SelfHostedRunner from the input data.
        # Pydantic does not correctly parse labels, they are of type fastcore.foundation.L.
        """
        github_dict["labels"] = list(github_dict["labels"])
        github_dict["instance_id"] = instance_id
        github_dict["metadata"] = RunnerMetadata(
            platform_name="github", runner_id=github_dict["id"]
        )
        return cls.parse_obj(github_dict)


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


class JITConfig(TypedDict, total=True):
    """JIT Config Token reply from GitHub API.

    Attributes:
        encoded_jit_config: The Token that identifies the runner.
        runner: Information about the runner associated with the JIT token.
    """

    encoded_jit_config: str
    runner: "JITConfigRunner"


class JITConfigRunner(TypedDict, total=True):
    """Runner Information returned when requesting a JIT token.

    Attributes:
        id: Id of the runner.
        status: Status of the runner.
        name: Name of the runner.
        os: OS of the runner.
        busy: Whether the runner is busy.
        labels: Labels of the runner.
    """

    id: int
    status: GitHubRunnerStatus
    name: str
    os: str
    busy: bool
    labels: "list[JITConfigRunnerLabel]"


class JITConfigRunnerLabel(TypedDict, total=True):
    """Labels for a runner returned when requesting a JIT token.

    Attributes:
        id: ID of the label.
        name: Name of the label.
        type: Type of label.
    """

    id: int
    name: str
    type: str
