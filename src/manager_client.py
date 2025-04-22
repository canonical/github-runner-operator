#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Client to interact with the service of github-runner-manager."""

import enum
import json
from urllib.parse import urljoin

import requests


class _HTTPMethod(str, enum.Enum):
    GET = "GET"
    POST = "POST"


class GitHubRunnerManagerClient:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._requests = requests.Session()
        self._base_url = f"http://{self._host}:{self._port}"

    def _request(self, method: str, path: str, *args, **kwargs):
        url = urljoin(self._base_url, path)
        response = self._requests.request(method, url, *args, **kwargs)
        response.raise_for_status()
        return response

    def check_runner(self) -> dict[str, str]:
        response = self._request(_HTTPMethod.GET, "/runner/check")
        return json.loads(response.text)

    def flush_runner(self, busy: bool = True):
        params = {"flush-busy": str(busy)}
        self._request(_HTTPMethod.POST, "/runner/flush", params=params)
