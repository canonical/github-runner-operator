#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.


"""Test for the jobmanager provider module."""

from unittest.mock import MagicMock

import pytest
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import (
    V1JobsJobIdTokenPost200Response,
)
from jobmanager_client.rest import ApiException

from github_runner_manager.errors import PlatformApiError
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.platform.jobmanager_provider import JobManagerPlatform, JobStatus
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunnerLabel


def test_get_runner_context_succeeds(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock the client api to return a token.
    act: Call get_runner_context.
    assert: The correct token and the correct runner are returned..
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.return_value = V1JobsJobIdTokenPost200Response(token="mytoken")

    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    instance_id = InstanceID.build(prefix="unit-0")
    labels = ["label"]
    platform = JobManagerPlatform()

    context, runner = platform.get_runner_context(metadata, instance_id, labels)

    assert "builder-agent" in context.shell_run_script
    assert runner.labels == [SelfHostedRunnerLabel(name="label")]
    assert runner.metadata == metadata
    assert runner.status == GitHubRunnerStatus.OFFLINE
    assert not runner.busy


@pytest.mark.parametrize(
    "api_return_value, error_message",
    [
        pytest.param(V1JobsJobIdTokenPost200Response(), "Empty token", id="No token"),
        pytest.param(ApiException, "API error", id="Exception from api"),
    ],
)
def test_get_runner_context_fails(
    monkeypatch: pytest.MonkeyPatch, api_return_value, error_message
):
    """
    arrange: Mock the jobmanager client to return different error conditions.
    act: Call get_runner_context.
    assert: PlatformApiError should be raised with the expected message.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = [api_return_value]

    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    instance_id = InstanceID.build(prefix="unit-0")
    labels = ["label"]
    platform = JobManagerPlatform()

    with pytest.raises(PlatformApiError) as exc:
        _context, _runner = platform.get_runner_context(metadata, instance_id, labels)

    assert error_message in str(exc.value)


@pytest.mark.parametrize(
    "api_return_value, picked_up",
    [
        pytest.param(Job(status=JobStatus.IN_PROGRESS.value), True, id="in progress job"),
        pytest.param(Job(status=JobStatus.PENDING.value), False, id="pending job"),
    ],
)
def test_check_job_been_picked_up(monkeypatch: pytest.MonkeyPatch, api_return_value, picked_up):
    """
    arrange: Prepare a job return for the jobmanager client.
    act: call check_job_been_picked_up.
    assert: Depending on the state of the job, it will be picked or not accordingly.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = [api_return_value]

    platform = JobManagerPlatform()
    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    job_url = "http://example.com/v1/jobs/3"

    assert platform.check_job_been_picked_up(metadata, job_url) == picked_up


def test_check_job_been_picked_fails(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: The jobmanager client raises an exception when called.
    act: call check_job_been_picked_up.
    assert: The PlatformApiError exception is raised from the jobmanager provider.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = ApiException

    platform = JobManagerPlatform()
    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    job_url = "http://example.com/v1/jobs/3"

    with pytest.raises(PlatformApiError):
        platform.check_job_been_picked_up(metadata, job_url)
