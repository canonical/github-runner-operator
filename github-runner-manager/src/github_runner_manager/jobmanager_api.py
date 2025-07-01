#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing logic to handle calls to the jobmanager api."""
import jobmanager_client
from jobmanager_client.exceptions import NotFoundException, ApiException
from pydantic import BaseModel, ValidationError
from urllib3.exceptions import RequestError


class JobManagerAPIException(Exception):
    """Base exception for JobManager API errors."""


class JobManagerAPINotFoundException(JobManagerAPIException):
    """Exception raised when a runner is not found in the JobManager API."""

class RunnerRegistration(BaseModel):
    id : int
    token: str

class RunnerHealth(BaseModel):
    status : str
    deletable: bool

class JobManagerAPI:

    def __init__(self, token: str, url: str):
        """Initialize the JobManagerAPI with a token and URL.
        Args:
            token: The authentication token for the JobManager API.
            url: The base URL for the JobManager API.
        """
        config = jobmanager_client.Configuration(host=url)
        self._api_client = jobmanager_client.ApiClient(configuration=config)
        self._api_client.set_default_header("Authorization", f"Bearer {token}")
        self._runners_api = jobmanager_client.RunnersApi(api_client=self._api_client)

    def get_runner_health(self, id: int) -> RunnerHealth:
        try:
            response = self._runners_api.get_runner_health_v1_runners_runner_id_health_get(id)
        except NotFoundException as err:
            raise JobManagerAPINotFoundException(
                f"Health for runner with ID {id} not found in JobManager API."
            ) from err
        except (ApiException, RequestError, ValueError) as exc:
            raise JobManagerAPIException(
                f"Error fetching runner health for ID {id}: {exc}"
            ) from exc
        return RunnerHealth(
            status=response.status,
            deletable=response.deletable
        )

    def register_runner(self, name: str, labels: list[str]):
        runner_register_request = jobmanager_client.RunnerCreate(
            name=name, labels=labels
        )

        try:
            response = self._runners_api.register_runner_v1_runners_register_post(
                runner_register_request
            )
        except NotFoundException as err:
            raise JobManagerAPINotFoundException(
                "Runner registration failed: JobManager API not found."
            ) from err
        except (ApiException, RequestError, ValueError) as exc:
            raise JobManagerAPIException(
                f"Error registering runner: {exc}"
            ) from exc
        return RunnerRegistration(id=response.id, token=response.token)

    def close(self):
        """Close the API client connection."""
        self._api_client.close()