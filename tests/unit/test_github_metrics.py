# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import errors
import github_metrics
from github_client import GithubClient
from github_type import JobConclusion, JobStats
from runner_metrics import PreJobMetrics


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

    github_client = MagicMock(spec=GithubClient)
    runner_name = secrets.token_hex(16)
    created_at = datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    started_at = created_at + timedelta(seconds=3600)
    github_client.get_job_info.return_value = JobStats(
        created_at=created_at,
        started_at=started_at,
        runner_name=runner_name,
        conclusion=JobConclusion.SUCCESS,
    )

    job_metrics = github_metrics.job(
        github_client=github_client, pre_job_metrics=pre_job_metrics, runner_name=runner_name
    )

    assert job_metrics.queue_duration == 3600
    assert job_metrics.conclusion == JobConclusion.SUCCESS


def test_job_job_not_found(pre_job_metrics: PreJobMetrics):
    """
    arrange: create a GithubClient mock which raises a JobNotFound exception.
    act: Call job.
    assert: a GithubMetricsError is raised.
    """
    github_client = MagicMock(spec=GithubClient)
    runner_name = secrets.token_hex(16)
    github_client.get_job_info.side_effect = errors.JobNotFoundError("Job not found")

    with pytest.raises(errors.GithubMetricsError):
        github_metrics.job(
            github_client=github_client, pre_job_metrics=pre_job_metrics, runner_name=runner_name
        )
