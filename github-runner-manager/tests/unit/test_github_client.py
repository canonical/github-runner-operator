# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import http
import json
import random
import secrets
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from github_runner_manager.errors import GithubApiError, JobNotFoundError, TokenError
from github_runner_manager.github_client import GithubClient
from github_runner_manager.types_.github import GitHubRepo, JobConclusion, JobInfo, JobStatus

JobStatsRawData = namedtuple(
    "JobStatsRawData",
    ["created_at", "started_at", "runner_name", "conclusion", "id", "status"],
)

TEST_URLLIB_RESPONSE_JSON = {"test": "test"}


@pytest.fixture(name="job_stats_raw")
def job_stats_fixture() -> JobStatsRawData:
    """Create a JobStats object."""
    runner_name = secrets.token_hex(16)
    return JobStatsRawData(
        created_at="2021-10-01T00:00:00Z",
        started_at="2021-10-01T01:00:00Z",
        conclusion="success",
        status="completed",
        runner_name=runner_name,
        id=random.randint(1, 1000),
    )


@pytest.fixture(name="urllib_urlopen_mock")
def urllib_open_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the urllib.request.urlopen function."""
    urllib_open_mock = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", urllib_open_mock)
    return urllib_open_mock


@pytest.fixture(name="github_client")
def github_client_fixture(
    job_stats_raw: JobStatsRawData, urllib_urlopen_mock: MagicMock
) -> GithubClient:
    """Create a GithubClient object with a mocked GhApi object."""
    gh_client = GithubClient("token")
    gh_client._client = MagicMock()
    gh_client._client.actions.list_jobs_for_workflow_run.return_value = {
        "jobs": [
            {
                "created_at": job_stats_raw.created_at,
                "started_at": job_stats_raw.started_at,
                "runner_name": job_stats_raw.runner_name,
                "conclusion": job_stats_raw.conclusion,
                "status": job_stats_raw.status,
                "id": job_stats_raw.id,
            }
        ]
    }
    urllib_urlopen_mock.return_value.__enter__.return_value.read.return_value = json.dumps(
        TEST_URLLIB_RESPONSE_JSON
    ).encode("utf-8")

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
                    "conclusion": job_stats_raw.conclusion,
                    "status": job_stats_raw.status,
                    "id": job_stats_raw.id,
                }
                for j in range(no_of_jobs_per_page)
            ]
        }
        for i in range(no_of_pages)
    ] + [{"jobs": []}]


def test_get_job_info_by_runner_name(github_client: GithubClient, job_stats_raw: JobStatsRawData):
    """
    arrange: A mocked Github Client that returns one page of jobs containing one job \
        with the runner.
    act: Call get_job_info_by_runner_name.
    assert: The correct JobStats object is returned.
    """
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info_by_runner_name(
        path=github_repo,
        workflow_run_id=secrets.token_hex(16),
        runner_name=job_stats_raw.runner_name,
    )
    assert job_stats == JobInfo(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
        conclusion=JobConclusion.SUCCESS,
        status=JobStatus.COMPLETED,
        job_id=job_stats_raw.id,
    )


def test_get_job_info_by_runner_name_no_conclusion(
    github_client: GithubClient, job_stats_raw: JobStatsRawData
):
    """
    arrange: A mocked Github Client that returns one page of jobs containing one job \
        with the runner with conclusion set to None.
    act: Call get_job_info_by_runner_name.
    assert: JobStats object with conclusion set to None is returned.
    """
    github_client._client.actions.list_jobs_for_workflow_run.return_value = {
        "jobs": [
            {
                "created_at": job_stats_raw.created_at,
                "started_at": job_stats_raw.started_at,
                "runner_name": job_stats_raw.runner_name,
                "conclusion": None,
                "status": job_stats_raw.status,
                "id": job_stats_raw.id,
            }
        ]
    }
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info_by_runner_name(
        path=github_repo,
        workflow_run_id=secrets.token_hex(16),
        runner_name=job_stats_raw.runner_name,
    )
    assert job_stats == JobInfo(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
        conclusion=None,
        status=JobStatus.COMPLETED,
        job_id=job_stats_raw.id,
    )


def test_get_job_info(github_client: GithubClient, job_stats_raw: JobStatsRawData):
    """
    arrange: A mocked Github Client that returns a response.
    act: Call get_job_info.
    assert: The response is returned.
    """
    github_client._client.actions.get_job_for_workflow_run.return_value = {
        "created_at": job_stats_raw.created_at,
        "started_at": job_stats_raw.started_at,
        "runner_name": job_stats_raw.runner_name,
        "conclusion": job_stats_raw.conclusion,
        "status": job_stats_raw.status,
        "id": job_stats_raw.id,
    }
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info(path=github_repo, job_id=job_stats_raw.id)
    assert job_stats == JobInfo(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
        conclusion=JobConclusion.SUCCESS,
        status=JobStatus.COMPLETED,
        job_id=job_stats_raw.id,
    )


def test_github_api_pagination_multiple_pages(
    github_client: GithubClient, job_stats_raw: JobStatsRawData
):
    """
    arrange: A mocked Github Client that returns multiple pages of jobs containing \
        one job with the runner.
    act: Call get_job_info.
    assert: The correct JobStats object is returned.
    """
    _mock_multiple_pages_for_job_response(
        github_client=github_client, job_stats_raw=job_stats_raw, include_runner=True
    )

    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    job_stats = github_client.get_job_info_by_runner_name(
        path=github_repo,
        workflow_run_id=secrets.token_hex(16),
        runner_name=job_stats_raw.runner_name,
    )
    assert job_stats == JobInfo(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        runner_name=job_stats_raw.runner_name,
        conclusion=JobConclusion.SUCCESS,
        status=JobStatus.COMPLETED,
        job_id=job_stats_raw.id,
    )


def test_github_api_pagination_job_not_found(
    github_client: GithubClient, job_stats_raw: JobStatsRawData
):
    """
    arrange: A mocked Github Client that returns multiple pages of jobs containing \
        no job with the runner.
    act: Call get_job_info.
    assert: An exception is raised.
    """
    _mock_multiple_pages_for_job_response(
        github_client=github_client, job_stats_raw=job_stats_raw, include_runner=False
    )

    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))

    with pytest.raises(JobNotFoundError):
        github_client.get_job_info_by_runner_name(
            path=github_repo,
            workflow_run_id=secrets.token_hex(16),
            runner_name=job_stats_raw.runner_name,
        )


def test_github_api_http_error(github_client: GithubClient, job_stats_raw: JobStatsRawData):
    github_client._client.actions.list_jobs_for_workflow_run.side_effect = HTTPError(
        "http://test.com", 500, "", http.client.HTTPMessage(), None
    )
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))

    with pytest.raises(JobNotFoundError):
        github_client.get_job_info_by_runner_name(
            path=github_repo,
            workflow_run_id=secrets.token_hex(16),
            runner_name=job_stats_raw.runner_name,
        )


def test_catch_http_errors(github_client: GithubClient):
    """
    arrange: A mocked Github Client that raises a 500 HTTPError.
    act: Call  an API endpoint.
    assert: A GithubApiError is raised.
    """
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    github_client._client.actions.create_remove_token_for_repo.side_effect = HTTPError(
        "http://test.com", 500, "", http.client.HTTPMessage(), None
    )

    with pytest.raises(GithubApiError):
        github_client.get_runner_remove_token(github_repo)


def test_catch_http_errors_token_issues(github_client: GithubClient):
    """
    arrange: A mocked Github Client that raises a 401 HTTPError.
    act: Call an API endpoint.
    assert: A TokenError is raised.
    """
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    github_client._client.actions.create_remove_token_for_repo.side_effect = HTTPError(
        "http://test.com", 401, "", http.client.HTTPMessage(), None
    )

    with pytest.raises(TokenError):
        github_client.get_runner_remove_token(github_repo)
