# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for PlannerClient."""

import json
from types import SimpleNamespace

import requests

from github_runner_manager.planner_client import (
    PlannerClient,
    PlannerConfiguration,
)


class _FakeResponse:
    """Minimal Response-like object used to stub `requests.Response`."""

    def __init__(self, status_code: int = 200, lines: list[str] | None = None) -> None:
        """Minimal Response-like object used to stub `requests.Response`.

        Args:
            status_code: HTTP status code to emulate.
            lines: Lines yielded by `iter_lines()` for streaming tests.
        """
        self.status_code = status_code
        self._lines = lines or []
        self._closed = False

    def raise_for_status(self) -> None:
        """Raise an HTTPError if status is 4xx/5xx.

        Raises:
            HTTPError: When `status_code` indicates an error.
        """
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP error")

    def iter_lines(self, decode_unicode: bool = True):
        """Yield configured NDJSON lines for streaming tests.

        Args:
            decode_unicode: Included for compatibility; not used in stub.

        Yields:
            str: Individual NDJSON lines.
        """
        for line in self._lines:
            yield line

    def close(self) -> None:
        """Mark the response as closed (context manager support)."""
        self._closed = True

    def __enter__(self):
        """Enter the context manager and return self."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit the context manager, closing the response.

        Args:
            exc_type: Exception type, if any.
            exc: Exception instance, if any.
            tb: Traceback, if any.

        Returns:
            bool: False to propagate any exception.
        """
        self.close()
        return False


class _FakeSession:
    """Minimal Session-like object used to stub `requests.Session`."""

    def __init__(self) -> None:
        """Initialize the fake session."""
        self.last_get: SimpleNamespace | None = None

    def mount(self, *_args, **_kwargs):
        """Compatibility no-op for adapter mounting."""
        return None

    def get(self, url: str, headers: dict[str, str], timeout: int, stream: bool = False):
        """Record GET call parameters and return a default fake response.

        Args:
            url: The request URL.
            headers: Request headers.
            timeout: Request timeout in seconds.
            stream: Whether the response should be streamed.

        Returns:
            _FakeResponse: Default 200 response; tests monkeypatch this.
        """
        self.last_get = SimpleNamespace(url=url, headers=headers, timeout=timeout, stream=stream)
        # Default successful response; individual tests can monkeypatch this method
        return _FakeResponse(status_code=200)


def _fake_get_stream_response(lines: list[str], status_code: int = 200):
    """Build a stub `Session.get` returning stream lines (NDJSON).

    Args:
        lines: List of NDJSON lines to yield.
        status_code: HTTP status code for the response (default: 200).

    Returns:
        Callable: A function compatible with `Session.get` signature.
    """

    def _fake_get(url, headers, timeout, stream=False):
        """Return a fake streaming response yielding predefined lines.

        Args:
            url: Request URL (ignored by stub).
            headers: Request headers (ignored by stub).
            timeout: Request timeout in seconds (ignored by stub).
            stream: Whether streaming is requested (ignored by stub).

        Returns:
            _FakeResponse: Response configured with the provided NDJSON lines.
        """
        return _FakeResponse(status_code=status_code, lines=lines)

    return _fake_get


def test_stream_pressure_success(monkeypatch):
    """
    arrange: Fake session streams NDJSON lines with a blank heartbeat.
    act: Iterate over stream_pressure('small').
    assert: Yields expected pressure updates, skipping blank heartbeat lines.
    """
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    lines = [json.dumps({"small": 2}), "", json.dumps({"small": 5})]
    monkeypatch.setattr(fake_session, "get", _fake_get_stream_response(lines))

    updates = list(client.stream_pressure("small"))
    assert updates[0].pressure == 2
    assert updates[1].pressure == 5
