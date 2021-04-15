# Copyright {{ year }} {{ author }}
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, patch

from charm import GithubRunnerOperator
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def test_install(self):
        harness = Harness(GithubRunnerOperator)
        harness.begin()
        harness.charm._runner = Mock()
        harness.charm.on.install.emit()
        harness.charm._runner.download.assert_called()
        harness.charm._runner.setup_env.assert_called()

    @patch("subprocess.check_output")
    def test_register(self, check_output):
        harness = Harness(GithubRunnerOperator)
        harness.begin()
        action_event = Mock(params={"url": "example.com", "token": "mocktoken"})
        harness.charm._on_register_action(action_event)
        assert action_event.set_results.called
        args, kwargs = check_output.call_args
        assert "example.com" in args[0]
        assert "mocktoken" in args[0]
