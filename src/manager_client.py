#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Client to interact with the service of github-runner-manager."""

import enum
import json
import logging
from typing import Any
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


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

    def _request(self, method: str, path: str, *args: Any, **kwargs: Any):
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

    def check_runner(self) -> dict[str, str]:
        """Request to check the state of runner.

        Raises:
            HTTPError: HTTP error encountered.

        Returns:
            The information on the runners.
        """
        try:
            response = self._request(_HTTPMethod.GET, "/runner/check")
        except requests.HTTPError as err:
            if err.response is not None:
                logger.error("Check runner encountered error: %s", err.response.text)
            raise
        return json.loads(response.text)

    def flush_runner(self, busy: bool = True) -> None:
        """Request to flush the runners.

        Args:
            busy: Whether to flush the busy runners.
        Raises:
            HTTPError: HTTP error encountered.
        """
        params = {"flush-busy": str(busy)}
        try:
            self._request(_HTTPMethod.POST, "/runner/flush", params=params)
        except requests.HTTPError as err:
            if err.response is not None:
                logger.error("Check runner encountered error: %s", err.response.text)
            raise
