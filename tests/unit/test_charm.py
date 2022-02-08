# Copyright {{ year }} {{ author }}
# See LICENSE file for licensing details.

import unittest
from unittest.mock import call, patch

from charm import GithubRunnerOperator
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_install(self, run, wt):
        harness = Harness(GithubRunnerOperator)
        harness.begin()
        harness.charm.on.install.emit()
        calls = [
            call(["snap", "install", "lxd"], check=True),
            call(["lxd", "init", "--auto"], check=True),
        ]
        run.assert_has_calls(calls)

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_org_register(self, run, wt, rm):
        """Test org registration"""
        harness = Harness(GithubRunnerOperator)
        harness.update_config({"path": "mockorg", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.config_changed.emit()
        rm.assert_called_with("mockorg", "mocktoken", "github-runner", "container")

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_repo_register(self, run, wt, rm):
        """Test repo registration"""
        harness = Harness(GithubRunnerOperator)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.config_changed.emit()
        rm.assert_called_with("mockorg/repo", "mocktoken", "github-runner", "container")

    # def test_add_cron(self):
    #     """Test adding cron jobs."""
    #     event = "test-event"
    #     interval = "test-interval"
    #     harness = Harness(GithubRunnerOperator)
    #     harness.begin()
    #     harness.charm._add_cron(event, interval)
    #     harness.charm._remove_cron(event)
    #     calls = {}
    #     for mock_call in harness.charm._cron_tab.mock_calls:
    #         name, args, kwargs = mock_call
    #         calls[name] = {"args": args, "kwargs": kwargs}

    #     # Check add cron calls CronTab with expected action and interval
    #     print(type(calls), "\n")
    #     print(calls, "\n")
    #     print(harness.charm._cron_tab, "\n")
    #     assert calls["().new"]["kwargs"]["command"].split("/")[-1] == event
    #     assert interval in calls["().new().setall"]["args"]
    #     # Check that add and remove use same comment
    #     assert (
    #         calls["().new"]["kwargs"]["comment"] == calls["().find_comment"]["args"][0]
    #     )
