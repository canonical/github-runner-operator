#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from errors import LogrotateSetupError, SubprocessError
from metrics import RunnerInstalled, issue_event, setup_logrotate

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


def test_issue_metrics_logs_events(tmp_path: Path):
    """
    arrange: Change path of the metrics log
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
    arrange: Change paths for the logrotate config and the log file
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


def test_setup_logrotate_enables_logrotate_timer(exec_command: MagicMock):
    """
    arrange: Mock execute command to return error for the is-active call and
     non-error for the remaining calls.
    act: Setup logrotate
    assert: The commands to enable and start the logrotate timer are called
    """

    def side_effect(*args, **kwargs):
        if "is-active" in args[0]:
            return "", 1
        return "", 0

    exec_command.side_effect = side_effect

    setup_logrotate()

    assert (
        call(["/usr/bin/systemctl", "enable", "logrotate.timer"], check_exit=True)
        in exec_command.mock_calls
    )
    assert (
        call(["/usr/bin/systemctl", "start", "logrotate.timer"], check_exit=True)
        in exec_command.mock_calls
    )


def test_setup_logrotate_raises_error(exec_command: MagicMock):
    """
    arrange: Mock execute command to raise a SubprocessError
    act: Setup logrotate
    assert: The expected error is raised.
    """
    exec_command.side_effect = SubprocessError(
        cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr"
    )

    with pytest.raises(LogrotateSetupError):
        setup_logrotate()
