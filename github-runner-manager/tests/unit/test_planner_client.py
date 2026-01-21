# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from types import SimpleNamespace

import pytest

from github_runner_manager.planner_client import (
    PlannerApiError,
    PlannerClient,
    PlannerConfiguration,
)


class _FakeResponse:
    def __init__(
        self, status_code: int = 200, json_obj: dict | None = None, lines: list[str] | None = None
    ):
        self.status_code = status_code
        self._json_obj = json_obj or {}
        self._lines = lines or []
        self._closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception("HTTP error")

    def json(self) -> dict:
        return self._json_obj

    def iter_lines(self, decode_unicode: bool = True):
        for line in self._lines:
            yield line

    def close(self) -> None:
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class _FakeSession:
    def __init__(self):
        self.last_get = None

    def mount(self, *_args, **_kwargs):
        return None

    def get(self, url: str, headers: dict[str, str], timeout: int, stream: bool = False):
        self.last_get = SimpleNamespace(url=url, headers=headers, timeout=timeout, stream=stream)
        # Default successful response; individual tests can monkeypatch this method
        return _FakeResponse(status_code=200)


def test_get_flavor_success(monkeypatch):
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    def _fake_get(url, headers, timeout, stream=False):  # noqa: ARG001
        return _FakeResponse(status_code=200, json_obj={"name": "small", "labels": ["x"]})

    monkeypatch.setattr(fake_session, "get", _fake_get)

    flavor = client.get_flavor("small")
    assert flavor.name == "small"
    assert fake_session.last_get.headers["Authorization"] == "Bearer t"
    assert "/api/v1/flavors/small" in fake_session.last_get.url


def test_get_pressure_success(monkeypatch):
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    def _fake_get(url, headers, timeout, stream=False):  # noqa: ARG001
        return _FakeResponse(status_code=200, json_obj={"pressure": 0.42})

    monkeypatch.setattr(fake_session, "get", _fake_get)

    pressure = client.get_pressure("small")
    assert pressure.pressure == 0.42
    assert "/api/v1/flavors/small/pressure" in fake_session.last_get.url


def test_stream_pressure_success(monkeypatch):
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    def _fake_get(url, headers, timeout, stream=False):  # noqa: ARG001
        lines = [json.dumps({"pressure": 0.4}), "", json.dumps({"pressure": 0.5})]
        return _FakeResponse(status_code=200, lines=lines)

    monkeypatch.setattr(fake_session, "get", _fake_get)

    updates = list(client.stream_pressure("small"))
    assert updates[0].pressure == 0.4
    assert updates[1].pressure == 0.5
    assert "stream=true" in fake_session.last_get.url
    assert fake_session.last_get.stream is True


def test_get_flavor_error_raises(monkeypatch):
    cfg = PlannerConfiguration(base_url="http://localhost:8080", token="t")
    client = PlannerClient(cfg)

    fake_session = _FakeSession()
    monkeypatch.setattr(client, "_session", fake_session)

    def _fake_get(url, headers, timeout, stream=False):  # noqa: ARG001
        return _FakeResponse(status_code=500)

    monkeypatch.setattr(fake_session, "get", _fake_get)

    with pytest.raises(PlannerApiError):
        _ = client.get_flavor("small")
