# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest.mock
from pathlib import Path

import pytest

from tests.unit.mock import MockGhapiClient, MockLxdClient, MockRepoPolicyComplianceClient


@pytest.fixture(name="exec_command")
def exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path, exec_command):
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.service_token_path", Path(tmp_path / "mock_service_token")
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_systemd_service", Path(tmp_path / "systemd_service")
    )
    monkeypatch.setattr("charm.os", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.shutil", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr(
        "firewall.Firewall.get_host_ip", unittest.mock.MagicMock(return_value="10.0.0.1")
    )
    monkeypatch.setattr("firewall.Firewall.refresh_firewall", unittest.mock.MagicMock())
    monkeypatch.setattr("runner.execute_command", exec_command)
    monkeypatch.setattr("runner.shared_fs", unittest.mock.MagicMock())
    monkeypatch.setattr("metrics.execute_command", exec_command)
    monkeypatch.setattr("metrics.METRICS_LOG_PATH", Path(tmp_path / "metrics.log"))
    monkeypatch.setattr("metrics.LOGROTATE_CONFIG", Path(tmp_path / "github-runner-metrics"))

    monkeypatch.setattr("runner.time", unittest.mock.MagicMock())
    monkeypatch.setattr("github_client.GhApi", MockGhapiClient)
    monkeypatch.setattr("runner_manager_type.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager_type.LxdClient", MockLxdClient)
    monkeypatch.setattr("runner_manager.github_metrics", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.runner_logs", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.LxdClient", MockLxdClient)
    monkeypatch.setattr("runner_manager.shared_fs", unittest.mock.MagicMock())
    monkeypatch.setattr(
        "runner_manager.RepoPolicyComplianceClient", MockRepoPolicyComplianceClient
    )
    monkeypatch.setattr("utilities.time", unittest.mock.MagicMock())
