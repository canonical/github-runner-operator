# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import http
import random
import secrets
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from errors import JobNotFoundError
from github_client import GithubClient
from github_type import GithubJobStats
from runner_type import GithubRepo

JobStatsRawData = namedtuple(
    "JobStatsRawData",
    ["created_at", "started_at", "runner_name"],
)


@pytest.fixture(name="job_stats_raw")
def job_stats_fixture() -> JobStatsRawData:
    """Create a GithubJobStats object."""

    runner_name = secrets.token_hex(16)
    return JobStatsRawData(
        created_at="2021-10-01T00:00:00Z",
        started_at="2021-10-01T01:00:00Z",
        runner_name=runner_name,
    )


@pytest.fixture(name="github_client")
def github_client_fixture(job_stats_raw: JobStatsRawData) -> GithubClient:
    """Create a GithubClient object with a mocked GhApi object."""
    gh_client = GithubClient("token")
    gh_client._client = MagicMock()
    gh_client._client.actions.list_jobs_for_workflow_run.return_value = {
        "jobs": [
            {
                "created_at": job_stats_raw.created_at,
                "started_at": job_stats_raw.started_at,
                "runner_name": job_stats_raw.runner_name,
            }
        ]
    }

    return gh_client


def _mock_multiple_pages_for_job_response(
    github_client: GithubClient, job_stats_raw: JobStatsRawData, include_runner: bool = True
):
    """Mock the list_jobs_for_workflow_run to return multiple pages.

    Args:
        github_client: The GithubClient object to mock.
        job_stats_raw: The JobStatsRawData object to use for the response.
        include_runner: Whether to include the runner in the response for one of the jobs.
    """
    no_of_pages = random.choice(range(1, 5))
    no_of_jobs_per_page = random.choice(range(1, 4))
    runner_names = [secrets.token_hex(16) for _ in range(no_of_pages * no_of_jobs_per_page)]

    if include_runner:
        runner_names[random.choice(range(no_of_pages))] = job_stats_raw.runner_name

    github_client._client.actions.list_jobs_for_workflow_run.side_effect = [
        {
            "jobs": [
                {
                    "created_at": job_stats_raw.created_at,
                    "started_at": job_stats_raw.started_at,
                    "runner_name": runner_names[i * no_of_jobs_per_page + j],
                }
                for j in range(no_of_jobs_per_page)
            ]
        }
        for i in range(no_of_pages)
    ] + [{"jobs": []}]


def test_get_job_info(github_client: GithubClient, job_stats_raw: JobStatsRawData):
    """
    arrange: A mocked Github Client that returns one page of jobs containing one job
     with the runner.
    act: Call get_job_info.
    assert: The correct GithubJobStats object is returned.
    """
    github_repo = GithubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info(
        path=github_repo,
        workflow_run_id=secrets.token_hex(16),
        runner_name=job_stats_raw.runner_name,
    )
    assert job_stats == GithubJobStats(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
    )


def test_github_api_pagination_multiple_pages(
    github_client: GithubClient, job_stats_raw: JobStatsRawData
):
    """
    arrange: A mocked Github Client that returns multiple pages of jobs containing
     one job with the runner.
    act: Call get_job_info.
    assert: The correct GithubJobStats object is returned.
    """
    _mock_multiple_pages_for_job_response(
        github_client=github_client, job_stats_raw=job_stats_raw, include_runner=True
    )

    github_repo = GithubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info(
        path=github_repo,
        workflow_run_id=secrets.token_hex(16),
        runner_name=job_stats_raw.runner_name,
    )
    assert job_stats == GithubJobStats(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
    )


def test_github_api_pagination_job_not_found(
    github_client: GithubClient, job_stats_raw: JobStatsRawData
):
    """
    arrange: A mocked Github Client that returns multiple pages of jobs containing
     no job with the runner.
    act: Call get_job_info.
    assert: An exception is raised.
    """
    _mock_multiple_pages_for_job_response(
        github_client=github_client, job_stats_raw=job_stats_raw, include_runner=False
    )

    github_repo = GithubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))

    with pytest.raises(JobNotFoundError):
        github_client.get_job_info(
            path=github_repo,
            workflow_run_id=secrets.token_hex(16),
            runner_name=job_stats_raw.runner_name,
        )


def test_github_api_http_error(github_client: GithubClient, job_stats_raw: JobStatsRawData):
    github_client._client.actions.list_jobs_for_workflow_run.side_effect = HTTPError(
        "http://test.com", 500, "", http.client.HTTPMessage(), None
    )
    github_repo = GithubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))

    with pytest.raises(JobNotFoundError):
        github_client.get_job_info(
            path=github_repo,
            workflow_run_id=secrets.token_hex(16),
            runner_name=job_stats_raw.runner_name,
        )
