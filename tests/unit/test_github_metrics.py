#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import errors
import github_metrics
from github_client import GithubClient
from github_type import GithubJobStats
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


def test_job_duration(pre_job_metrics: PreJobMetrics):
    """
    arrange: create a GithubClient mock which returns a GithubJobStats object.
    act: Call job_queue_duration.
    assert: the duration is the difference between the job started_at and created_at.
    """

    github_client = MagicMock(spec=GithubClient)
    runner_name = secrets.token_hex(16)
    created_at = datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    started_at = created_at + timedelta(seconds=3600)
    github_client.get_job_info.return_value = GithubJobStats(
        created_at=created_at,
        started_at=started_at,
        runner_name=runner_name,
    )

    duration = github_metrics.job_queue_duration(
        github_client=github_client, pre_job_metrics=pre_job_metrics, runner_name=runner_name
    )

    assert duration == 3600


def test_job_duration_job_not_found(pre_job_metrics: PreJobMetrics):
    """
    arrange: create a GithubClient mock which raises a JobNotFound exception.
    act: Call job_queue_duration.
    assert: a GithubMetricsError is raised.
    """
    github_client = MagicMock(spec=GithubClient)
    runner_name = secrets.token_hex(16)
    github_client.get_job_info.side_effect = errors.JobNotFoundError("Job not found")

    with pytest.raises(errors.GithubMetricsError):
        github_metrics.job_queue_duration(
            github_client=github_client, pre_job_metrics=pre_job_metrics, runner_name=runner_name
        )
