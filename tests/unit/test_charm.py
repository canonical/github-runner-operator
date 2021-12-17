# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import call, patch

from charm import GithubRunnerOperator
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    @patch("runner.subprocess")
    def test_install(self, sp):
        harness = Harness(GithubRunnerOperator)
        harness.begin()
        harness.charm.on.install.emit()
        calls = [
            call(["sudo", "snap", "install", "lxd"]),
            call(["sudo", "lxd", "init", "--auto"]),
        ]
        sp.check_output.assert_has_calls(calls)

    def test_org_register(self):
        """Test org registration"""
        harness = Harness(GithubRunnerOperator)
        harness.update_config({"path": "mockorg", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.config_changed.emit()
        api = harness.charm._runner.api
        api.actions.create_registration_token_for_org.assert_called_with(org="mockorg")

    def test_repo_register(self):
        """Test repo registration"""
        harness = Harness(GithubRunnerOperator)
        harness.update_config({"path": "mockorg/repo", "token": "mocktoken"})
        harness.begin()
        harness.charm.on.config_changed.emit()
        api = harness.charm._runner.api
        api.actions.create_registration_token_for_repo.assert_called_with(
            owner="mockorg", repo="repo"
        )

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
