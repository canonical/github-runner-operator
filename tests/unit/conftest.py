# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest.mock
from pathlib import Path

import pytest

import openstack_manager
from tests.unit.mock import MockGhapiClient, MockLxdClient, MockRepoPolicyComplianceClient


@pytest.fixture(name="exec_command")
def exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


@pytest.fixture(name="lxd_exec_command")
def lxd_exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


@pytest.fixture(name="runner_binary_path")
def runner_binary_path_fixture(tmp_path):
    return tmp_path / "github-runner-app"


def disk_usage_mock(total_disk):
    disk = unittest.mock.MagicMock()
    disk.total = total_disk
    disk_usage = unittest.mock.MagicMock(return_value=disk)
    return disk_usage


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path, exec_command, lxd_exec_command, runner_binary_path):
    openstack_manager_mock = unittest.mock.MagicMock(spec=openstack_manager)

    cron_path = tmp_path / "cron.d"
    cron_path.mkdir()

    monkeypatch.setattr(
        "charm.GithubRunnerCharm.service_token_path", tmp_path / "mock_service_token"
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_web_service_path",
        tmp_path / "repo_policy_compliance_service",
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_systemd_service", tmp_path / "systemd_service"
    )
    monkeypatch.setattr("charm.openstack_manager", openstack_manager_mock)
    monkeypatch.setattr("charm.GithubRunnerCharm.kernel_module_path", tmp_path / "modules")
    monkeypatch.setattr("charm.GithubRunnerCharm._update_kernel", lambda self, now: None)
    monkeypatch.setattr("charm.execute_command", exec_command)
    monkeypatch.setattr("charm.shutil", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.shutil.disk_usage", disk_usage_mock(30 * 1024 * 1024 * 1024))
    monkeypatch.setattr("charm_state.CHARM_STATE_PATH", Path(tmp_path / "charm_state.json"))
    monkeypatch.setattr("charm_state.openstack_manager", openstack_manager_mock)
    monkeypatch.setattr("event_timer.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("event_timer.execute_command", exec_command)
    monkeypatch.setattr(
        "firewall.Firewall.get_host_ip", unittest.mock.MagicMock(return_value="10.0.0.1")
    )
    monkeypatch.setattr("firewall.Firewall.refresh_firewall", unittest.mock.MagicMock())
    monkeypatch.setattr("runner.execute_command", lxd_exec_command)
    monkeypatch.setattr("runner.shared_fs", unittest.mock.MagicMock())
    monkeypatch.setattr("metrics.execute_command", lxd_exec_command)
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
    monkeypatch.setattr("runner_manager.execute_command", exec_command)
    monkeypatch.setattr("runner_manager.RunnerManager.runner_bin_path", runner_binary_path)
    monkeypatch.setattr("runner_manager.RunnerManager.cron_path", cron_path)
    monkeypatch.setattr(
        "runner_manager.RepoPolicyComplianceClient", MockRepoPolicyComplianceClient
    )
    monkeypatch.setattr("utilities.time", unittest.mock.MagicMock())
