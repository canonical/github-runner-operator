#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Client to interact with the service of github-runner-manager."""

import enum
import functools
import json
import logging
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from errors import RunnerManagerServiceConnectionError, RunnerManagerServiceResponseError

logger = logging.getLogger(__name__)

NO_RESPONSE_ERROR_MESSAGE = "Failed request with no response"
CONNECTION_ERROR_MESSAGE = "Failed request due to connection failure"


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
        response = self._request(_HTTPMethod.GET, "/runner/check")
        runner_info = json.loads(response.text)
        runner_info["runners"] = tuple(runner_info["runners"])
        runner_info["busy_runners"] = tuple(runner_info["busy_runners"])
        runner_info = {key.replace("_", "-"): value for key, value in runner_info.items()}
        return runner_info

    @catch_requests_errors
    def flush_runner(self, busy: bool = True) -> None:
        """Request to flush the runners.

        Args:
            busy: Whether to flush the busy runners.
        """
        params = {"flush-busy": str(busy)}
        self._request(_HTTPMethod.POST, "/runner/flush", params=params)
