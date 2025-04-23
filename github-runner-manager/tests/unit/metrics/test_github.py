#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
from datetime import datetime, timedelta, timezone
from random import randint
from unittest.mock import MagicMock

import pytest

from github_runner_manager.errors import GithubMetricsError, JobNotFoundError
from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.metrics import github as github_metrics
from github_runner_manager.metrics.runner import PreJobMetrics
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.types_.github import JobConclusion, JobInfo, JobStatus


@pytest.fixture(name="pre_job_metrics")
def pre_job_metrics_fixture() -> PreJobMetrics:
    """Create a PreJobMetrics object."""
    return PreJobMetrics(
        repository="owner/repo",
        workflow_run_id=1,
        workflow="workflow",
        job_name="job",
        job_started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        timestamp=1234567890,
        event="push",
    )


def test_job(pre_job_metrics: PreJobMetrics):
    """
    arrange: create a GithubClient mock which returns a GithubJobStats object.
    act: Call job.
    assert: the job metrics are returned.
    """
    prefix = "app-0"
    github_client = MagicMock(spec=GithubClient)
    runner = InstanceID.build(prefix=prefix)
    created_at = datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    started_at = created_at + timedelta(seconds=3600)
    github_client.get_job_info_by_runner_name.return_value = JobInfo(
        created_at=created_at,
        started_at=started_at,
        conclusion=JobConclusion.SUCCESS,
        status=JobStatus.COMPLETED,
        job_id=randint(1, 1000),
    )

    github_provider = GitHubRunnerPlatform(
        prefix=prefix, path="canonical", github_client=github_client
    )
    job_metrics = github_metrics.job(
        platform_provider=github_provider,
        pre_job_metrics=pre_job_metrics,
        runner=runner,
        metadata=RunnerMetadata(),
    )

    assert job_metrics.queue_duration == 3600
    assert job_metrics.conclusion == JobConclusion.SUCCESS


def test_job_job_not_found(pre_job_metrics: PreJobMetrics):
    """
    arrange: create a GithubClient mock which raises a JobNotFound exception.
    act: Call job.
    assert: a GithubMetricsError is raised.
    """
    prefix = "app-0"
    github_client = MagicMock(spec=GithubClient)
    runner = InstanceID.build(prefix=prefix)
    github_client.get_job_info_by_runner_name.side_effect = JobNotFoundError("Job not found")
    github_provider = GitHubRunnerPlatform(
        prefix=prefix, path="canonical", github_client=github_client
    )

    with pytest.raises(GithubMetricsError):
        github_metrics.job(
            platform_provider=github_provider,
            metadata=RunnerMetadata(),
            pre_job_metrics=pre_job_metrics,
            runner=runner,
        )
