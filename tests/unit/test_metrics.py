#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path
from unittest.mock import MagicMock

from metrics import RunnerInstalled, issue_event, setup_logrotate

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


def test_issue_metrics_logs_events(tmp_path: Path):
    """
    arrange: Mock
    act: Issue a metric event
    assert: The expected metric log is created
    """
    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    issue_event(event)

    assert json.loads(tmp_path.joinpath("metrics.log").read_text()) == {
        "event": "runner_installed",
        "timestamp": 123,
        "flavor": "small",
        "duration": 456,
    }


def test_setup_logrotate(tmp_path: Path):
    """
    arrange: Changed paths for the logrotate config and the log file.
    act: Setup logrotate
    assert: The expected logrotate config is created
    """

    setup_logrotate()

    logrotate_path = tmp_path / "github-runner-metrics"
    metrics_log_path = tmp_path / "metrics.log"

    expected_logrotate_config = f"""{metrics_log_path} {{
    rotate 0
    missingok
    notifempty
    create
}}
"""
    assert logrotate_path.read_text() == expected_logrotate_config


def test_setup_logrotate_enables_logrotate_timer(tmp_path: Path, exec_command: MagicMock):
    """
    arrange: Mock execute command to return error for the first call and
     non-error for the second call.
    act: Setup logrotate
    assert: The expected logrotate config is created
    """
    exec_command.side_effect = [("", 1), ("", 0)]

    setup_logrotate()

    exec_command.assert_called_with(
        ["/usr/bin/systemctl", "enable", "logrotate.timer"], check_exit=True
    )
