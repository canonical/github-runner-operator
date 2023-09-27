# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for GithubRunnerCharm."""
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, call, patch

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import GithubRunnerCharm
from errors import MissingConfigurationError, RunnerError, SubprocessError
from github_type import GitHubRunnerStatus
from runner_manager import RunnerInfo, RunnerManagerConfig
from runner_type import GitHubOrg, GitHubRepo, VirtualMachineResources


def raise_runner_error(*args, **kargs):
    raise RunnerError("mock error")


def raise_subprocess_error(*args, **kargs):
    raise SubprocessError(cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr")


def raise_url_error(*args, **kargs):
    raise urllib.error.URLError("mock error")


def mock_get_latest_runner_bin_url():
    mock = MagicMock()
    mock.download_url = "www.example.com"
    return mock


def mock_get_github_info():
    return [
        RunnerInfo("test runner 0", GitHubRunnerStatus.ONLINE.value, True),
        RunnerInfo("test runner 1", GitHubRunnerStatus.ONLINE.value, False),
        RunnerInfo("test runner 2", GitHubRunnerStatus.OFFLINE.value, False),
        RunnerInfo("test runner 3", GitHubRunnerStatus.OFFLINE.value, False),
        RunnerInfo("test runner 4", "unknown", False),
    ]


class TestCharm(unittest.TestCase):
    """Test cases for GithubRunnerCharm."""

    @patch.dict(
        os.environ,
        {
            "JUJU_CHARM_HTTPS_PROXY": "http://proxy.server:1234",
            "JUJU_CHARM_HTTP_PROXY": "http://proxy.server:1234",
            "JUJU_CHARM_NO_PROXY": "127.0.0.1,localhost",
        },
    )
    def test_proxy_setting(self):
        harness = Harness(GithubRunnerCharm)
        harness.begin()

        assert harness.charm.proxies["https"] == "http://proxy.server:1234"
        assert harness.charm.proxies["http"] == "http://proxy.server:1234"
        assert harness.charm.proxies["no_proxy"] == "127.0.0.1,localhost"

    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    @patch("builtins.open")
    def test_install(self, open, run, wt):
        harness = Harness(GithubRunnerCharm)
        harness.begin()
        harness.charm.on.install.emit()
        calls = [
            call(
                ["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"],
                capture_output=True,
                shell=False,
                check=False,
            ),
            call(
                ["/snap/bin/lxd", "init", "--auto"], capture_output=True, shell=False, check=False
            ),
        ]
        run.assert_has_calls(calls, any_order=True)

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_org_register(self, run, wt, mkdir, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config(
            {
                "path": "mockorg",
                "token": "mocktoken",
                "group": "mockgroup",
                "reconcile-interval": 5,
            }
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        token = harness.charm.service_token
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GitHubOrg(org="mockorg", group="mockgroup"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.ram_pool_path,
            ),
            proxies={},
            issue_metrics=False,
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_repo_register(self, run, wt, mkdir, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config(
            {"path": "mockorg/repo", "token": "mocktoken", "reconcile-interval": 5}
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        token = harness.charm.service_token
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GitHubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.ram_pool_path,
            ),
            proxies={},
            issue_metrics=False,
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_update_config(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url
        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        # update to 0 virtual machines
        harness.update_config({"virtual-machines": 0})
        harness.charm.on.reconcile_runners.emit()
        token = harness.charm.service_token
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GitHubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.ram_pool_path,
            ),
            proxies={},
            issue_metrics=False,
        )
        mock_rm.reconcile.assert_called_with(0, VirtualMachineResources(2, "7GiB", "10GiB")),
        mock_rm.reset_mock()

        # update to 10 VMs with 4 cpu and 7GiB memory
        harness.update_config({"virtual-machines": 10, "vm-cpu": 4})
        harness.charm.on.reconcile_runners.emit()
        token = harness.charm.service_token
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GitHubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.ram_pool_path,
            ),
            proxies={},
            issue_metrics=False,
        )
        mock_rm.reconcile.assert_called_with(
            10, VirtualMachineResources(cpu=4, memory="7GiB", disk="10GiB")
        )
        mock_rm.reset_mock()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_stop(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.stop.emit()
        mock_rm.flush.assert_called()

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_get_runner_manager(self, run, wt, mkdir):
        harness = Harness(GithubRunnerCharm)
        harness.begin()

        # Get runner manager via input.
        assert harness.charm._get_runner_manager("mocktoken", "mockorg/repo") is not None

        with self.assertRaises(MissingConfigurationError):
            harness.charm._get_runner_manager()

        # Get runner manager via config.
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        assert harness.charm._get_runner_manager() is not None

        # With invalid path.
        assert harness.charm._get_runner_manager("mocktoken", "mock/invalid/path") is None

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    @patch("builtins.open")
    def test_on_install_failure(self, open, run, wt, mkdir, rm):
        """Test various error thrown during install."""

        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url

        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        # Base case: no error thrown.
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == ActiveStatus()

        GithubRunnerCharm._install_deps = raise_subprocess_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == BlockedStatus("Failed to install dependencies")

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_start_failure(self, run, wt, mkdir, rm):
        """Test various error thrown during install."""
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url

        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        harness.charm._reconcile_runners = raise_runner_error
        harness.charm.on.start.emit()
        assert harness.charm.unit.status == MaintenanceStatus(
            "Failed to start runners: mock error"
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        mock_event = MagicMock()

        mock_rm.get_github_info = mock_get_github_info

        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        harness.charm._on_check_runners_action(mock_event)
        mock_event.set_results.assert_called_with(
            {"online": 2, "offline": 2, "unknown": 1, "runners": "test runner 0, test runner 1"}
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action_with_errors(self, run, wt, mkdir, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        # No config
        harness.charm._on_check_runners_action(mock_event)
        mock_event.fail.assert_called_with(
            "Missing required charm configuration: ['token', 'path']"
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_flush_runners_action(self, run, wt, mkdir, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        harness.charm._on_flush_runners_action(mock_event)
        mock_event.fail.assert_called_with(
            "Missing required charm configuration: ['token', 'path']"
        )
        mock_event.reset_mock()

        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.charm._on_flush_runners_action(mock_event)
        mock_event.set_results.assert_called()
        mock_event.reset_mock()
