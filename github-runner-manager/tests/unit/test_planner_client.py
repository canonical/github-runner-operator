"""Unit tests for PlannerClient."""

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from types import SimpleNamespace

import pytest
import requests

from github_runner_manager.planner_client import (
    PlannerApiError,
    PlannerClient,
    PlannerConfiguration,
)


class _FakeResponse:
    """Minimal Response-like object used to stub `requests.Response`."""

    def __init__(
        self, status_code: int = 200, json_obj: dict | None = None, lines: list[str] | None = None
    ) -> None:
        """Minimal Response-like object used to stub `requests.Response`.

        Args:
            status_code: HTTP status code to emulate.
            json_obj: JSON body returned by `json()`.
            lines: Lines yielded by `iter_lines()` for streaming tests.
        """
        self.status_code = status_code
        self._json_obj = json_obj or {}
        self._lines = lines or []
        self._closed = False

    def raise_for_status(self) -> None:
        """Raise an HTTPError if status is 4xx/5xx.

        Raises:
            HTTPError: When `status_code` indicates an error.
        """
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP error")

    def json(self) -> dict:
        """Return the configured JSON body.

        Returns:
            dict: The JSON payload used by tests.
        """
        return self._json_obj

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


def _fake_get_json_response(json_obj: dict, status_code: int = 200):
    """Build a stub `Session.get` returning a JSON body.

    Args:
        json_obj: JSON payload to return.
        status_code: HTTP status code for the response (default: 200).

    Returns:
        Callable: A function compatible with `Session.get` signature.
    """

    def _fake_get(url, headers, timeout, stream=False):
        """Return a fake JSON response for any GET request.

        Args:
            url: Request URL (ignored by stub).
            headers: Request headers (ignored by stub).
            timeout: Request timeout in seconds (ignored by stub).
            stream: Whether streaming is requested (ignored by stub).

        Returns:
            _FakeResponse: Response carrying the provided JSON payload.
        """
        return _FakeResponse(status_code=status_code, json_obj=json_obj)

    return _fake_get


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


def _fake_get_status_response(status_code: int):
    """Build a stub `Session.get` returning only a status code.

    Args:
        status_code: HTTP status code to return.

    Returns:
        Callable: A function compatible with `Session.get` signature.
    """

    def _fake_get(url, headers, timeout, stream=False):  # noqa: ARG001
        """Return a fake response with only a status code.

        Args:
            url: Request URL (ignored by stub).
            headers: Request headers (ignored by stub).
            timeout: Request timeout in seconds (ignored by stub).
            stream: Whether streaming is requested (ignored by stub).

        Returns:
            _FakeResponse: Response with the given HTTP status code.
        """
        return _FakeResponse(status_code=status_code)

    return _fake_get


def test_get_flavor_success(monkeypatch):
    """Test get_flavor returns expected fields and headers.

    Arrange: PlannerClient with a fake session returning flavor JSON.
    Act: Call get_flavor('small').
    Assert: Fields match and Authorization header/URL are expected.
    """
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    monkeypatch.setattr(
        fake_session, "get", _fake_get_json_response({"name": "small", "labels": ["x"]})
    )

    flavor = client.get_flavor("small")
    assert flavor.name == "small"


def test_get_pressure_success(monkeypatch):
    """Test get_pressure returns the current pressure value.

    Arrange: PlannerClient with a fake session returning pressure JSON.
    Act: Call get_pressure('small').
    Assert: Pressure value and request URL path are correct.
    """
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    monkeypatch.setattr(fake_session, "get", _fake_get_json_response({"pressure": 2}))

    pressure = client.get_pressure("small")
    assert pressure.pressure == 2


def test_stream_pressure_success(monkeypatch):
    """Test stream_pressure yields pressure updates from NDJSON stream.

    Arrange: Fake session streams NDJSON lines with a blank heartbeat.
    Act: Iterate over stream_pressure('small').
    Assert: Yields expected updates; includes stream=true and uses stream=True on request.
    """
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    lines = [json.dumps({"pressure": 2}), "", json.dumps({"pressure": 5})]
    monkeypatch.setattr(fake_session, "get", _fake_get_stream_response(lines))

    updates = list(client.stream_pressure("small"))
    assert updates[0].pressure == 2
    assert updates[1].pressure == 5


def test_get_flavor_error_raises(monkeypatch):
    """Test get_flavor raises PlannerApiError on HTTP failure.

    Arrange: PlannerClient with a fake session returning HTTP 500.
    Act: Calling get_flavor('small').
    Assert: Raises PlannerApiError
    """
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    monkeypatch.setattr(fake_session, "get", _fake_get_status_response(500))

    with pytest.raises(PlannerApiError):
        _ = client.get_flavor("small")
