# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest.mock
from pathlib import Path

import pytest

from tests.unit.mock import MockGhapiClient, MockLxdClient, MockRepoPolicyComplianceClient


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.service_token_path", Path(tmp_path / "mock_service_token")
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_systemd_service", Path(tmp_path / "systemd_service")
    )
    monkeypatch.setattr("charm.os", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.shutil", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("runner.time", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.GhApi", MockGhapiClient)
    monkeypatch.setattr("runner_manager.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.LxdClient", MockLxdClient)
    monkeypatch.setattr(
        "runner_manager.RepoPolicyComplianceClient", MockRepoPolicyComplianceClient
    )
    monkeypatch.setattr("utilities.time", unittest.mock.MagicMock())
