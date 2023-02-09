# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for GithubRunnerCharm.

TODO: Convert the test to using pytest.
"""

import unittest
import urllib.error
from subprocess import CalledProcessError  # nosec B404
from unittest.mock import MagicMock, call, patch

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import GithubRunnerCharm
from errors import RunnerError
from github_type import GitHubRunnerStatus
from runner_manager import RunnerInfo
from runner_type import GitHubOrg, GitHubRepo, VirtualMachineResources


def raise_error(*args, **kargs):
    raise Exception("mock error")


def raise_runner_error(*args, **kargs):
    raise RunnerError("mock error")


def raise_called_process_error(*args, **kargs):
    raise CalledProcessError(returncode=1, cmd="mock cmd")


def raise_url_error(*args, **kargs):
    raise urllib.error.URLError("mock error")


def mock_get_latest_runner_bin_url():
    mock = MagicMock()
    mock.download_url = "www.example.com"
    return mock


class TestCharm(unittest.TestCase):
    """Test cases for GithubRunnerCharm."""

    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_install(self, run, wt):
        harness = Harness(GithubRunnerCharm)
        harness.begin()
        harness.charm.on.install.emit()
        calls = [
            call(
                ["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"],
                capture_output=True,
                shell=False,
            ),
            call(["/snap/bin/lxd", "init", "--auto"], capture_output=True, shell=False),
        ]
        run.assert_has_calls(calls, any_order=True)

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_org_register(self, run, wt, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg", "token": "mocktoken", "reconcile-interval": 5})
        harness.begin()
        harness.charm.on.config_changed.emit()
        rm.assert_called_with(
            GitHubOrg(org="mockorg"), "mocktoken", "github-runner", 5, proxies={}
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_repo_register(self, run, wt, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config(
            {"path": "mockorg/repo", "token": "mocktoken", "reconcile-interval": 5}
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        rm.assert_called_with(
            GitHubRepo(owner="mockorg", repo="repo"), "mocktoken", "github-runner", 5, proxies={}
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_update_config(self, run, wt, rm):
        rm.return_value = mock_rm = MagicMock()
        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        # update to 10 containers
        harness.update_config({"containers": 10, "virtual-machines": 0})
        harness.charm.on.reconcile_runners.emit()
        rm.assert_called_with(
            GitHubRepo(owner="mockorg", repo="repo"), "mocktoken", "github-runner", 5, proxies={}
        )
        mock_rm.reconcile.assert_called_with(0, VirtualMachineResources(2, "7GiB", "10GiB")),
        mock_rm.reset_mock()

        # update to 10 VMs with 4 cpu and 7GiB memory
        harness.update_config({"containers": 0, "virtual-machines": 10, "vm-cpu": 4})
        harness.charm.on.reconcile_runners.emit()
        rm.assert_called_with(
            GitHubRepo(owner="mockorg", repo="repo"), "mocktoken", "github-runner", 5, proxies={}
        )
        mock_rm.reconcile.assert_called_with(
            10, VirtualMachineResources(cpu=4, memory="7GiB", disk="10GiB")
        )
        mock_rm.reset_mock()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_stop(self, run, wt, rm):
        rm.return_value = mock_rm = MagicMock()
        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.stop.emit()
        mock_rm.flush.assert_called()

    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_get_runner_manager(self, run, wt):
        harness = Harness(GithubRunnerCharm)
        harness.begin()

        # Get runner manager via input.
        assert harness.charm._get_runner_manager("mocktoken", "mockorg/repo") is not None

        assert harness.charm._get_runner_manager() is None

        # Get runner manager via config.
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        assert harness.charm._get_runner_manager() is not None

        # With invalid path.
        assert harness.charm._get_runner_manager("mocktoken", "mock/invalid/path") is None

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_install_failure(self, run, wt, rm):
        """Test various error thrown during install."""

        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url

        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        # Base case: no error thrown.
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == ActiveStatus()

        harness.charm._reconcile_runners = raise_runner_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == MaintenanceStatus(
            "Failed to start runners: mock error"
        )

        harness.charm._reconcile_runners = raise_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == BlockedStatus("mock error")

        mock_rm.update_runner_bin = raise_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == MaintenanceStatus(
            "Failed to update runner binary: mock error"
        )

        GithubRunnerCharm._install_deps = raise_called_process_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == MaintenanceStatus("Failed to install dependencies")

        GithubRunnerCharm._install_deps = raise_error
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == BlockedStatus("mock error")

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_update_runner_bin(self, run, wt, rm):
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url

        harness = Harness(GithubRunnerCharm)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()

        harness.charm.on.update_runner_bin.emit()

        mock_rm.get_latest_runner_bin_url = raise_error
        harness.charm.on.update_runner_bin.emit()
        assert harness.charm.unit.status == BlockedStatus("mock error")

        mock_rm.get_latest_runner_bin_url = raise_url_error
        harness.charm.on.update_runner_bin.emit()
        assert harness.charm.unit.status == BlockedStatus(
            "Failed to check for runner updates: <urlopen error mock error>"
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action(self, run, wt, rm):
        def mock_get_github_info():
            return [
                RunnerInfo("test runner 0", GitHubRunnerStatus.online),
                RunnerInfo("test runner 1", GitHubRunnerStatus.online),
                RunnerInfo("test runner 2", GitHubRunnerStatus.offline),
                RunnerInfo("test runner 3", GitHubRunnerStatus.offline),
                RunnerInfo("test runner 4", "unknown"),
            ]

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
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action_with_errors(self, run, wt, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        # No config
        harness.charm._on_check_runners_action(mock_event)
        mock_event.fail.assert_called_with("Missing token or org/repo path config")

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_flush_runners_action(self, run, wt, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        harness.charm._on_flush_runners_action(mock_event)
        mock_event.fail.assert_called_with("Missing token or org/repo path config")
        mock_event.reset_mock()

        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.charm._on_flush_runners_action(mock_event)
        mock_event.set_results.assert_called()
        mock_event.reset_mock()

        harness.charm._reconcile_runners = raise_error
        harness.charm._on_flush_runners_action(mock_event)
        mock_event.fail.assert_called()
        mock_event.reset_mock()
