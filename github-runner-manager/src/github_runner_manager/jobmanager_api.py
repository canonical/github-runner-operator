#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing logic to handle calls to the jobmanager api."""
from enum import Enum

import jobmanager_client
from jobmanager_client.exceptions import ApiException, NotFoundException
from pydantic import BaseModel
from urllib3.exceptions import RequestError


class JobManagerAPIError(Exception):
    """Base exception for JobManager API errors."""


class JobManagerAPINotFoundError(JobManagerAPIError):
    """Exception raised when a runner is not found in the JobManager API."""


class JobStatus(str, Enum):
    """Status of a job on the JobManager.

    Attributes:
        IN_PROGRESS: Represents a job that is in progress.
        PENDING: Represents a job that is pending.
    """

    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"


class Job(BaseModel):
    """Represents a job on the JobManagerAPI.

    Attributes:
        status: The status of the job.
    """

    status: str | None


class RunnerStatus(str, Enum):
    """Status of a runner on the JobManager.

    Attributes:
        IN_PROGRESS: Represents a job that is in progress.
        PENDING: Represents a job that is pending.
    """

    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"


class RunnerRegistration(BaseModel):
    """Represents a runner registration response from the JobManagerAPI.

    Attributes:
        id: The ID of the registered runner.
        token: The token for the registered runner.
    """

    id: int
    token: str


class RunnerHealth(BaseModel):
    """Represents the health status of a runner on the JobManagerAPI.

    Attributes:
        status: The health status of the runner.
        deletable: Indicates if the runner can be deleted.
    """

    status: str
    deletable: bool


class JobManagerAPI:
    """Handles interactions with the JobManager API."""

    def __init__(self, token: str, url: str):
        """Initialize the JobManagerAPI with a token and URL.

        Args:
            token: The authentication token for the JobManager API.
            url: The base URL for the JobManager API.
        """
        config = jobmanager_client.Configuration(host=url)
        self._api_client = jobmanager_client.ApiClient(configuration=config)
        self._api_client.set_default_header("Authorization", f"Bearer {token}")
        self._jobs_api = jobmanager_client.JobsApi(api_client=self._api_client)
        self._runners_api = jobmanager_client.RunnersApi(api_client=self._api_client)

    def get_runner_health(self, runner_id: int) -> RunnerHealth:
        """Fetch the health status of a runner by its ID from the JobManager API.

        Args:
            runner_id: The ID of the runner to fetch health status for.

        Raises:
            JobManagerAPINotFoundError: If the runner with the given ID is not found.
            JobManagerAPIError: If there is an error fetching the runner health.

        Returns:
            RunnerHealth: The health status of the runner.
        """
        try:
            response = self._runners_api.get_runner_health_v1_runners_runner_id_health_get(
                runner_id
            )
        except NotFoundException as err:
            raise JobManagerAPINotFoundError(
                f"Health for runner with ID {runner_id} not found in JobManager API."
            ) from err
        except (ApiException, RequestError, ValueError) as exc:
            raise JobManagerAPIError(
                f"Error fetching runner health for ID {runner_id}: {exc}"
            ) from exc
        return RunnerHealth(status=response.status, deletable=response.deletable)

    def register_runner(self, name: str, labels: list[str]) -> RunnerRegistration:
        """Register a new runner with the JobManager API.

        Args:
            name: The name of the runner to register.
            labels: A list of labels to associate with the runner.

        Returns:
            RunnerRegistration: The registration details of the runner, including ID and token.

        Raises:
            JobManagerAPIError: If there is an error registering the runner.
        """
        runner_register_request = jobmanager_client.RunnerCreate(name=name, labels=labels)

        try:
            response = self._runners_api.register_runner_v1_runners_register_post(
                runner_register_request
            )
        except (ApiException, RequestError, ValueError) as exc:
            raise JobManagerAPIError(f"Error registering runner: {exc}") from exc
        return RunnerRegistration(id=response.id, token=response.token)

    def get_job(self, job_id: int) -> Job:
        """Fetch a job by its ID from the JobManager API.

        Args:
            job_id: The ID of the job to fetch.

        Returns:
            Job: The job object containing its status.

        Raises:
            JobManagerAPINotFoundError: If the job with the given ID is not found.
            JobManagerAPIError: If there is an error fetching the job.
        """
        try:
            response = self._jobs_api.get_job_v1_jobs_job_id_get(job_id)
        except NotFoundException as err:
            raise JobManagerAPINotFoundError(
                f"Job with ID {job_id} not found in JobManager API."
            ) from err
        except (ApiException, RequestError, ValueError) as exc:
            raise JobManagerAPIError(f"Error fetching job with ID {job_id}: {exc}") from exc
        return Job(status=response.status)

    def close(self) -> None:
        """Close the API client connection."""
        self._api_client.close()
