# Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for jobmanager client."""
import secrets
from unittest.mock import MagicMock

import pytest
from jobmanager_client import RunnerHealthResponse, ValidationError, RunnerRegisterResponse, \
    JobRead
from jobmanager_client.exceptions import NotFoundException, ApiException
from urllib3.exceptions import RequestError

from github_runner_manager.jobmanager_api import JobManagerAPI, RunnerHealth, \
    JobManagerAPINotFoundException, JobManagerAPIException, RunnerRegistration, JobStatus, Job, \
    RunnerStatus


@pytest.fixture(name="token")
def token_fixture():
    return secrets.token_hex(8)

@pytest.fixture(name="url")
def url_fixture():
    return "http://jobmanager.internal"

@pytest.fixture(name="jobmanager_api")
def jobmanager_api(token, url):
    jobmanager_api = JobManagerAPI(token=token,url=url)
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
    jobmanager_api = JobManagerAPI(token=token,url=url)
    assert "Authorization" in jobmanager_api._api_client.default_headers
    assert jobmanager_api._api_client.default_headers["Authorization"] == f"Bearer {token}"
    assert jobmanager_api._api_client.configuration.host == url
    assert jobmanager_api._jobs_api.api_client == jobmanager_api._api_client
    assert jobmanager_api._runners_api.api_client == jobmanager_api._api_client

def test_jobmanager_close(jobmanager_api):
    """
    arrange: Create a jobmanager api object
    act: Call the JobManagerAPI close method
    assert: The api_client's close method is calle
    """
    jobmanager_api.close()

    jobmanager_api._api_client.close.assert_called_once()


def test_jobmanager_api_get_runner_health(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the get_runner_health_v1_runners_runner_id_health_get method.
    act: Call get_runner_health method.
    assert: The method returns a RunnerHealth object.
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        return_value=                RunnerHealthResponse(
                    label="label",
                    status=RunnerStatus.IN_PROGRESS.value,
                    deletable=True,
                    cpu_usage="10%",
                    ram_usage="20%",
                    disk_usage="30%",
                ),)
    response = jobmanager_api.get_runner_health(id=123)
    assert RunnerHealth(status=RunnerStatus.IN_PROGRESS, deletable=True) == response

def test_jobmanager_api_get_runner_health_not_found(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the get_runner_health_v1_runners_runner_id_health_get method to return a 404
    act: Call get_runner_health method.
    assert: The method returns a JobManagerNotFound exception
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        side_effect=NotFoundException("Runner not found"))

    with pytest.raises(JobManagerAPINotFoundException):
        jobmanager_api.get_runner_health(id=123)

@pytest.mark.parametrize(
    "exception",
    [pytest.param(ApiException(), id="ApiException"),
                  pytest.param(RequestError(None, None, None), id="RequestError"),
     pytest.param(ValueError(), id="ValueError")]
)
def test_jobmanager_api_get_runner_health_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the get_runner_health_v1_runners_runner_id_health_get method to raise an exception
    act: Call get_runner_health method.
    assert: The method raises the exception
    """
    jobmanager_api._runners_api.get_runner_health_v1_runners_runner_id_health_get = MagicMock(
        side_effect=exception
    )

    with pytest.raises(JobManagerAPIException):
        jobmanager_api.get_runner_health(id=123)

def test_jobmanager_api_register_runner(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the register_runner_v1_runners_register_post method.
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
    [pytest.param(ApiException(), id="ApiException"),
                  pytest.param(RequestError(None, None, None), id="RequestError"),
     pytest.param(ValueError(), id="ValueError")]
)
def test_jobmanager_api_register_runner_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the register_runner_v1_runners_register_post method to raise an exception
    act: Call get_runner_health method.
    assert: The method raises the exception
    """
    jobmanager_api._runners_api.register_runner_v1_runners_register_post = MagicMock(
        side_effect=exception
    )

    with pytest.raises(JobManagerAPIException):
        jobmanager_api.register_runner(name="test-runner", labels=["label1", "label2"])

def test_jobmanager_api_get_job(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the get_job_v1_jobs_job_id_get method.
    act: Call get_runner_health method.
    assert: The method returns a Job object.
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(
        return_value=                JobRead(
                status=JobStatus.IN_PROGRESS.value,
                architecture="arm64",
                base_series="jammy",
                id=1,
                requested_by="foobar",
            )
                )
    response = jobmanager_api.get_job(id=123)
    assert Job(status=JobStatus.IN_PROGRESS) == response


def test_jobmanager_api_get_job_not_found(jobmanager_api):
    """
    arrange: Create a jobmanager api object and stub the get_job_v1_jobs_job_id_get method to return a 404
    act: Call get_job method.
    assert: The method returns a JobManagerNotFound exception
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(
        side_effect=NotFoundException("Job not found"))

    with pytest.raises(JobManagerAPINotFoundException):
        jobmanager_api.get_job(id=123)

@pytest.mark.parametrize(
    "exception",
    [pytest.param(ApiException(), id="ApiException"),
                  pytest.param(RequestError(None, None, None), id="RequestError"),
     pytest.param(ValueError(), id="ValueError")]
)
def test_jobmanager_api_get_job_error(jobmanager_api, exception):
    """
    arrange: Create a jobmanager api object and stub the get_job_v1_jobs_job_id_get method to raise an exception
    act: Call get_job method.
    assert: The method raises the exception
    """
    jobmanager_api._jobs_api.get_job_v1_jobs_job_id_get = MagicMock(
        side_effect=exception
    )

    with pytest.raises(JobManagerAPIException):
        jobmanager_api.get_job(id=123)