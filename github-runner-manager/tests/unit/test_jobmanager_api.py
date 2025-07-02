# Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for jobmanager client."""
import secrets
from unittest.mock import MagicMock

import pytest
from jobmanager_client import (
    JobRead,
    RunnerHealthResponse,
    RunnerRegisterResponse,
)
from jobmanager_client.exceptions import ApiException, NotFoundException
from urllib3.exceptions import RequestError

from github_runner_manager.jobmanager_api import (
    Job,
    JobManagerAPI,
    JobManagerAPIError,
    JobManagerAPINotFoundError,
    JobStatus,
    RunnerHealth,
    RunnerRegistration,
    RunnerStatus,
)


@pytest.fixture(name="token")
def token_fixture():
    return secrets.token_hex(8)


@pytest.fixture(name="url")
def url_fixture():
    return "http://jobmanager.internal"


@pytest.fixture(name="jobmanager_api")
def jobmanager_api(token, url):
    jobmanager_api = JobManagerAPI(token=token, url=url)
    api_client = MagicMock()
    jobmanager_api._api_client = api_client
    jobmanager_api._runners_api = MagicMock()
    jobmanager_api._jobs_api = MagicMock()
    jobmanager_api._runners_api.api_client = jobmanager_api._jobs_api.api_client = api_client
    return jobmanager_api


def test_jobmanager_api_initialize(token, url):
    """
    arrange: Arrange a dummy token and URL.
    act: Created jobmanager api object.
    assert: Default headers of underlying client are set to bearer authorization and url is set.
    """
    jobmanager_api = JobManagerAPI(token=token, url=url)
    assert "Authorization" in jobmanager_api._api_client.default_headers
    assert jobmanager_api._api_client.default_headers["Authorization"] == f"Bearer {token}"
    assert jobmanager_api._api_client.configuration.host == url
    assert jobmanager_api._jobs_api.api_client == jobmanager_api._api_client
    assert jobmanager_api._runners_api.api_client == jobmanager_api._api_client


def test_jobmanager_close(jobmanager_api):
    """
    arrange: Create a jobmanager api object.
    act: Call the JobManagerAPI close method
    assert: The api_client's close method is called
    """
    jobmanager_api.close()

    jobmanager_api._api_client.close.assert_called_once()


def test_jobmanager_api_get_runner_health(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the api client method.
    act: Call get_runner_health method.
    assert: The method returns a RunnerHealth object.
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        return_value=RunnerHealthResponse(
            label="label",
            status=RunnerStatus.IN_PROGRESS.value,
            deletable=True,
            cpu_usage="10%",
            ram_usage="20%",
            disk_usage="30%",
        ),
    )
    response = jobmanager_api.get_runner_health(runner_id=123)
    assert RunnerHealth(status=RunnerStatus.IN_PROGRESS, deletable=True) == response


def test_jobmanager_api_get_runner_health_not_found(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the api client method to return a 404.
    act: Call get_runner_health method.
    assert: The method returns a JobManagerNotFound exception
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        side_effect=NotFoundException("Runner not found")
    )

    with pytest.raises(JobManagerAPINotFoundError):
        jobmanager_api.get_runner_health(runner_id=123)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ApiException(), id="ApiException"),
        pytest.param(RequestError(MagicMock(), MagicMock(), MagicMock()), id="RequestError"),
        pytest.param(ValueError(), id="ValueError"),
    ],
)
def test_jobmanager_api_get_runner_health_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the api client method to raise an exception.
    act: Call get_runner_health method.
    assert: The method raises the exception
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        side_effect=exception
    )

    with pytest.raises(JobManagerAPIError):
        jobmanager_api.get_runner_health(runner_id=123)


def test_jobmanager_api_register_runner(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the api client method.
    act: Call register_runner method.
    assert: The method returns a RunnerRegistration object.
    """
    jobmanager_api._runners_api.register_runner_v1_runners_register_post = MagicMock(
        return_value=RunnerRegisterResponse(id=123, token="token")
    )
    response = jobmanager_api.register_runner(name="test-runner", labels=["label1", "label2"])
    assert response == RunnerRegistration(id=123, token="token")


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ApiException(), id="ApiException"),
        pytest.param(RequestError(MagicMock(), MagicMock(), MagicMock()), id="RequestError"),
        pytest.param(ValueError(), id="ValueError"),
    ],
)
def test_jobmanager_api_register_runner_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the api client method to raise an exception.
    act: Call get_runner_health method.
    assert: The method raises the exception
    """
    jobmanager_api._runners_api.register_runner_v1_runners_register_post = MagicMock(
        side_effect=exception
    )

    with pytest.raises(JobManagerAPIError):
        jobmanager_api.register_runner(name="test-runner", labels=["label1", "label2"])


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(JobStatus.PENDING.value, id="PENDING"),
        pytest.param(JobStatus.IN_PROGRESS.value, id="IN_PROGRESS"),
        pytest.param(None, id="None"),
    ],
)
def test_jobmanager_api_get_job(jobmanager_api, status):
    """
    arrange: Create a jobmanager api object and stub the api client method.
    act: Call get_runner_health method.
    assert: The method returns a Job object.
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(
        return_value=JobRead(
            status=status,
            architecture="arm64",
            base_series="jammy",
            id=1,
            requested_by="foobar",
        )
    )
    response = jobmanager_api.get_job(job_id=123)
    assert Job(status=status) == response


def test_jobmanager_api_get_job_not_found(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the api client method to return a 404.
    act: Call get_job method.
    assert: The method returns a JobManagerNotFound exception
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(
        side_effect=NotFoundException("Job not found")
    )

    with pytest.raises(JobManagerAPINotFoundError):
        jobmanager_api.get_job(job_id=123)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ApiException(), id="ApiException"),
        pytest.param(RequestError(MagicMock(), MagicMock(), MagicMock()), id="RequestError"),
        pytest.param(ValueError(), id="ValueError"),
    ],
)
def test_jobmanager_api_get_job_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the api client method to raise an exception.
    act: Call get_job method.
    assert: The method raises the exception
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(side_effect=exception)

    with pytest.raises(JobManagerAPIError):
        jobmanager_api.get_job(job_id=123)
