# Copyright 2025 Canonical Ltd.
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
import requests

# HTTP404NotFoundError is not found by pylint
from fastcore.net import HTTP404NotFoundError  # pylint: disable=no-name-in-module
from requests import HTTPError as RequestsHTTPError

import github_runner_manager.github_client
from github_runner_manager.configuration.github import GitHubOrg, GitHubRepo
from github_runner_manager.errors import JobNotFoundError, PlatformApiError, TokenError
from github_runner_manager.github_client import GithubClient, GithubRunnerNotFoundError
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.types_.github import (
    GitHubRunnerStatus,
    JobConclusion,
    JobInfo,
    JobStatus,
    SelfHostedRunner,
    SelfHostedRunnerLabel,
)

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


def test_list_runners(github_client: GithubClient, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A mocked Github Client that returns two runners, one for the requested prefix.
    act: Call list_runners with the prefix.
    assert: A correct runners is returned, the one matching the prefix.
    """
    response = {
        "total_count": 2,
        "runners": [
            {
                "id": 311,
                "name": "current-unit-0-n-e8bc54023ae1",
                "os": "linux",
                "status": "offline",
                "busy": True,
                "labels": [
                    {"id": 0, "name": "openstack_test", "type": "read-only"},
                    {"id": 0, "name": "test-ae7a1fbcd0c1", "type": "read-only"},
                    {"id": 0, "name": "self-hosted", "type": "read-only"},
                    {"id": 0, "name": "linux", "type": "read-only"},
                ],
            },
            {
                "id": 312,
                "name": "anotherunit-0-n-e8bc54023ae1",
                "os": "linux",
                "status": "offline",
                "busy": True,
                "labels": [
                    {"id": 0, "name": "openstack_test", "type": "read-only"},
                    {"id": 0, "name": "test-ae7a1fbcd0c1", "type": "read-only"},
                    {"id": 0, "name": "self-hosted", "type": "read-only"},
                    {"id": 0, "name": "linux", "type": "read-only"},
                ],
            },
        ],
    }

    github_client._client.last_page.return_value = 1
    github_client._client.actions.list_self_hosted_runners_for_repo.side_effect = response

    pages = MagicMock()
    pages.return_value = [response]
    monkeypatch.setattr(github_runner_manager.github_client, "pages", pages)

    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    runners = github_client.list_runners(path=github_repo, prefix="current-unit-0")

    assert len(runners) == 1
    runner0 = runners[0]
    assert runner0.id == response["runners"][0]["id"]  # type: ignore
    assert runner0.instance_id.name == response["runners"][0]["name"]  # type: ignore
    assert runner0.busy == response["runners"][0]["busy"]  # type: ignore
    assert runner0.status == response["runners"][0]["status"]  # type: ignore


def test_catch_http_errors(github_client: GithubClient):
    """
    arrange: A mocked Github Client that raises a 500 HTTPError.
    act: Call  an API endpoint.
    assert: A PlatformApiError is raised.
    """
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    github_client._client.actions.create_remove_token_for_repo.side_effect = HTTPError(
        "http://test.com", 500, "", http.client.HTTPMessage(), None
    )

    with pytest.raises(PlatformApiError):
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


def test_get_runner_context_repo(github_client: GithubClient):
    """
    arrange: A mocked GitHub client that replies with information about jitconfig for repo.
    act: Call get_runner_registration_jittoken.
    assert: The jittoken is extracted from the returned value.
    """
    instance_id = InstanceID.build("test-runner")
    github_repo = GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16))
    github_client._client.actions.generate_runner_jitconfig_for_repo.return_value = {
        "runner": {
            "id": 113,
            "name": instance_id.name,
            "os": "unknown",
            "status": "offline",
            "busy": False,
            "labels": [
                {"id": 0, "name": "label1", "type": "read-only"},
                {"id": 0, "name": "label2", "type": "read-only"},
            ],
            "runner_group_id": 1,
        },
        "encoded_jit_config": "hugestringinhere",
    }

    labels = ["label1", "label2"]
    jittoken, runner = github_client.get_runner_registration_jittoken(
        path=github_repo, instance_id=instance_id, labels=labels
    )

    assert jittoken == "hugestringinhere"
    assert runner == SelfHostedRunner(
        busy=False,
        id=113,
        labels=[SelfHostedRunnerLabel(name="label1"), SelfHostedRunnerLabel(name="label2")],
        status=GitHubRunnerStatus.OFFLINE,
        instance_id=instance_id,
        metadata=RunnerMetadata(platform_name="github", runner_id=113),
    )


def test_catch_http_errors_from_getting_runner_group_id(
    github_client: GithubClient, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: A mocked Github Client that raises a 500 HTTPError when getting the runner group id.
    act: Call
    assert: A PlatformApiError is raised.
    """
    github_repo = GitHubOrg(org="theorg", group="my group name")
    instance_id = InstanceID.build("test-runner")
    labels = ["label1", "label2"]

    def _mock_get(url, headers, *args, **kwargs):
        """Mock for requests.get."""

        class _Response:
            """Mocked Response for requests.get."""

            def raise_for_status(self):
                """Mocked raise_for_status.

                Raises:
                   RequestsHTTPError: HTTPError from requests. This is a fake response.
                """
                self.status_code = 500
                raise RequestsHTTPError("500 Server Error", response=self)  # type: ignore

        return _Response()

    monkeypatch.setattr(requests, "get", _mock_get)
    with pytest.raises(PlatformApiError):
        _, _ = github_client.get_runner_registration_jittoken(
            path=github_repo, instance_id=instance_id, labels=labels
        )


def test_get_runner_context_org(github_client: GithubClient, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A mocked GitHub client that replies with information about jitconfig for org.
       The requests library is patched to return information about github runner groups.
    act: Call get_runner_registration_jittoken for the org.
    assert: The API for the jittoken is called with the correct arguments, like the runner_group_id
       and the jittoken is extracted from the returned value.
    """
    # The code that this test executes is not covered by integration tests.
    github_repo = GitHubOrg(org="theorg", group="my group name")

    def _mock_get(url, headers, *args, **kwargs):
        """Mock for requests.get."""

        class _Response:
            """Mocked Response for requests.get."""

            @staticmethod
            def json():
                """Json response for requests.get mock.

                Returns:
                   The JSON response from the API.
                """
                return {
                    "total_count": 2,
                    "runner_groups": [
                        {
                            "id": 1,
                            "name": "Default",
                            "visibility": "all",
                            "allows_public_repositories": True,
                            "default": True,
                            "workflow_restrictions_read_only": False,
                            "restricted_to_workflows": False,
                            "selected_workflows": [],
                            "runners_url": "https://api.github.com/orgs/theorg/....",
                            "hosted_runners_url": "https://api.github.com/orgs/theorg/....",
                            "inherited": False,
                        },
                        {
                            "id": 3,
                            "name": "my group name",
                            "visibility": "all",
                            "allows_public_repositories": True,
                            "default": False,
                            "workflow_restrictions_read_only": False,
                            "restricted_to_workflows": False,
                            "selected_workflows": [],
                            "runners_url": "https://api.github.com/orgs/theorg/....",
                            "hosted_runners_url": "https://api.github.com/orgs/theorg/....",
                            "inherited": False,
                        },
                    ],
                }

            def raise_for_status(self):
                """Mocked raise_for_status."""
                pass

        assert (
            url
            == f"https://api.github.com/orgs/{github_repo.org}/actions/runner-groups?per_page=100"
        )
        assert headers["Authorization"] == "Bearer token"
        return _Response()

    monkeypatch.setattr(requests, "get", _mock_get)

    instance_id = InstanceID.build("test-runner")

    def _mock_generate_runner_jitconfig_for_org(org, name, runner_group_id, labels):
        """Mocked generate_runner_jitconfig_for_org."""
        assert org == "theorg"
        assert name == instance_id.name
        assert runner_group_id == 3
        assert labels == ["label1", "label2"]
        return {
            "runner": {
                "id": 18,
                "name": instance_id.name,
                "os": "unknown",
                "status": "offline",
                "busy": False,
                "labels": [
                    {"id": 0, "name": "self-hosted", "type": "read-only"},
                    {"id": 0, "name": "X64", "type": "read-only"},
                ],
                "runner_group_id": 3,
            },
            "encoded_jit_config": "anotherhugetoken",
        }

    github_client._client.actions.generate_runner_jitconfig_for_org.side_effect = (
        _mock_generate_runner_jitconfig_for_org
    )

    labels = ["label1", "label2"]
    jittoken, github_runner = github_client.get_runner_registration_jittoken(
        path=github_repo, instance_id=instance_id, labels=labels
    )

    assert jittoken == "anotherhugetoken"
    assert github_runner == SelfHostedRunner(
        busy=False,
        id=18,
        labels=[SelfHostedRunnerLabel(name="self-hosted"), SelfHostedRunnerLabel(name="X64")],
        status=GitHubRunnerStatus.OFFLINE,
        instance_id=instance_id,
        metadata=RunnerMetadata(platform_name="github", runner_id=18),
    )


@pytest.mark.parametrize(
    "github_repo",
    [
        pytest.param(
            GitHubOrg(org=secrets.token_hex(16), group=secrets.token_hex(16)), id="Org runner"
        ),
        pytest.param(
            GitHubRepo(owner=secrets.token_hex(16), repo=secrets.token_hex(16)), id="Repo runner"
        ),
    ],
)
def test_get_runner(
    github_client: GithubClient,
    monkeypatch: pytest.MonkeyPatch,
    github_repo: GitHubOrg | GitHubRepo,
):
    """
    arrange: A mocked GhAPI Client that returns a runner based on the github repo or org.
    act: Call get_runner in GithubClient.
    assert: The runner is returned correctly returned.
    """
    prefix = "unit-0"
    runner_id = 1

    raw_runner = {
        "id": runner_id,
        "name": f"{prefix}-99e88ff9d9ce",
        "os": "linux",
        "status": "offline",
        "busy": False,
        "labels": [
            {"id": 0, "name": "openstack_test", "type": "read-only"},
            {"id": 0, "name": "linux", "type": "read-only"},
            {"id": 0, "name": "self-hosted", "type": "read-only"},
            {"id": 0, "name": "test-89be82ae89d6", "type": "read-only"},
        ],
    }

    if isinstance(github_repo, GitHubRepo):
        mocked_ghapi_function = github_client._client.actions.get_self_hosted_runner_for_repo
    else:
        mocked_ghapi_function = github_client._client.actions.get_self_hosted_runner_for_org
    mocked_ghapi_function.return_value = raw_runner

    github_runner = github_client.get_runner(github_repo, prefix, runner_id)

    assert github_runner
    assert github_runner.id == runner_id
    assert github_runner.metadata.runner_id == str(runner_id)


def test_get_runner_not_found(
    github_client: GithubClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: A mocked GhApi Github Client that raises 404 when a runner is requested.
    act: Call get_runner in GithubClient.
    assert: The exception GithubRunnerNotFoundError is raised.
    """
    path = GitHubOrg(org=secrets.token_hex(16), group=secrets.token_hex(16))
    prefix = "unit-0"
    runner_id = 1
    github_client._client.actions.get_self_hosted_runner_for_org.side_effect = (
        HTTP404NotFoundError("", {}, None)
    )
    with pytest.raises(GithubRunnerNotFoundError):
        _ = github_client.get_runner(path, prefix, runner_id)
