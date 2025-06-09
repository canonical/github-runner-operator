#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Client to interact with the service of github-runner-manager."""

import enum
import functools
import json
import logging
from time import sleep
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from errors import (
    RunnerManagerServiceConnectionError,
    RunnerManagerServiceNotReadyError,
    RunnerManagerServiceResponseError,
)

logger = logging.getLogger(__name__)

NO_RESPONSE_ERROR_MESSAGE = "Failed request with no response"
CONNECTION_ERROR_MESSAGE = "Failed request due to connection failure"
NOT_READY_ERROR_MESSAGE = "GitHub runner manager service not ready"


def catch_requests_errors(func: Callable) -> Callable:
    """Decorate for handling requests errors.

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.
    """

    @functools.wraps(func)
    def func_with_error_handling(*args: Any, **kwargs: Any) -> Any:
        """Add requests error handling to the function.

        Args:
            args: The arguments of the function.
            kwargs: The keyword arguments of the function.

        Raises:
            RunnerManagerServiceResponseError: Error in the response from the manager service.
            RunnerManagerServiceConnectionError: Error in connecting to the manager service.

        Returns:
            The return value of the function.
        """
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            if err.response is None:
                raise RunnerManagerServiceResponseError(NO_RESPONSE_ERROR_MESSAGE) from err
            logger.error(
                "Failed request with code %s: %s", err.response.status_code, err.response.text
            )
            raise RunnerManagerServiceResponseError(
                f"Failed request with code {err.response.status_code}: {err.response.text}"
            ) from err
        except requests.ConnectionError as err:
            raise RunnerManagerServiceConnectionError(CONNECTION_ERROR_MESSAGE) from err

    return func_with_error_handling


class _HTTPMethod(str, enum.Enum):
    """HTTP Methods available for client.

    Attributes:
        GET: The GET method.
        POST: The POST method.
    """

    GET = "GET"
    POST = "POST"


class GitHubRunnerManagerClient:
    """Client for GitHub Runner Manager service."""

    def __init__(self, host: str, port: int):
        """Construct the object.

        Args:
            host: The host address of the manager service.
            port: The port for the  manager service.
        """
        self._host = host
        self._port = port
        self._requests = requests.Session()
        self._base_url = f"http://{self._host}:{self._port}"

    # Issuing request will be tested in integration tests.
    def _request(
        self, method: str, path: str, *args: Any, **kwargs: Any
    ) -> requests.Response:  # pragma: no cover
        """Make a HTTP request to the manager service.

        This uses the requests library, additional arguments can be passed by `args` and `kwargs`.

        Args:
            method: The HTTP method to make the request, e.g., GET, POST.
            path: The URL path of the request.
            args: Additional arguments to pass to requests.
            kwargs: Additional keyword arguments to pass to requests.
        """
        url = urljoin(self._base_url, path)
        response = self._requests.request(method, url, *args, **kwargs)
        response.raise_for_status()
        return response

    @catch_requests_errors
    def check_runner(self) -> dict[str, str]:
        """Request to check the state of runner.

        Returns:
            The information on the runners.
        """
        self.wait_till_ready()
        response = self._request(_HTTPMethod.GET, "/runner/check")
        runner_info = json.loads(response.text)
        runner_info["runners"] = tuple(runner_info["runners"])
        runner_info["busy_runners"] = tuple(runner_info["busy_runners"])
        runner_info = {key.replace("_", "-"): value for key, value in runner_info.items()}
        return runner_info

    @catch_requests_errors
    def flush_runner(self, busy: bool = False) -> None:
        """Request to flush the runners.

        Args:
            busy: Whether to flush the busy runners.
        """
        self.wait_till_ready()
        params = {"flush-busy": str(busy)}
        self._request(_HTTPMethod.POST, "/runner/flush", params=params)

    def health_check(self) -> None:
        """Request a health check on the runner manager service.

        This is used as a readiness check since the service does not have a dedicated readiness
        endpoint.

        Raises:
            RunnerManagerServiceNotReadyError: The runner manager service is not ready for
                API requests.
        """
        try:
            response = self._request(_HTTPMethod.GET, "/health")
        except requests.HTTPError as err:
            raise RunnerManagerServiceNotReadyError(NOT_READY_ERROR_MESSAGE) from err
        except requests.ConnectionError as err:
            raise RunnerManagerServiceNotReadyError(NOT_READY_ERROR_MESSAGE) from err

        if response.status_code != 204:
            raise RunnerManagerServiceNotReadyError(NOT_READY_ERROR_MESSAGE)

    def wait_till_ready(self) -> None:
        """Wait till the runner manager service is ready for requests."""
        for _ in range(8):
            try:
                self.health_check()
            except RunnerManagerServiceNotReadyError:
                pass
            else:
                return
            sleep(15)
        # RunnerManagerServiceNotReadyError will be raised if the service is still not unhealthy.
        self.health_check()
