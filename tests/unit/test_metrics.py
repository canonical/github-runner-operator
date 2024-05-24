# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import metrics
from errors import LogrotateSetupError, SubprocessError

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


def test_issue_metrics_logs_events(tmp_path: Path):
    """
    arrange: Change path of the metrics log.
    act: Issue a metric event.
    assert: The expected metric log is created.
    """
    event = metrics.RunnerInstalled(timestamp=123, flavor="small", duration=456)

    metrics.issue_event(event)

    assert json.loads(metrics.METRICS_LOG_PATH.read_text()) == {
        "event": "runner_installed",
        "timestamp": 123,
        "flavor": "small",
        "duration": 456,
    }


def test_issue_metrics_exclude_none_values(tmp_path: Path):
    """
    arrange: Change path of the metrics log.
    act: Issue a metric event with a None value.
    assert: The expected metric log without the None value is created.
    """
    event = metrics.RunnerStop(
        timestamp=123,
        flavor="small",
        workflow="workflow",
        repo="repo",
        github_event="github_event",
        status="status",
        status_info=None,
        job_duration=456,
    )

    metrics.issue_event(event)

    assert json.loads(metrics.METRICS_LOG_PATH.read_text()) == {
        "event": "runner_stop",
        "timestamp": 123,
        "flavor": "small",
        "workflow": "workflow",
        "repo": "repo",
        "github_event": "github_event",
        "status": "status",
        "job_duration": 456,
    }


def test_setup_logrotate(tmp_path: Path):
    """
    arrange: Change paths for the logrotate config and the log file.
    act: Setup logrotate.
    assert: The expected logrotate config is created.
    """
    metrics.setup_logrotate()

    expected_logrotate_config = f"""{metrics.METRICS_LOG_PATH} {{
    rotate 0
    missingok
    notifempty
    create
}}
"""
    assert metrics.LOGROTATE_CONFIG.read_text() == expected_logrotate_config


def test_setup_logrotate_enables_logrotate_timer(lxd_exec_command: MagicMock):
    """
    arrange: Mock execute command to return error for the is-active call and \
        non-error for the remaining calls.
    act: Setup logrotate.
    assert: The commands to enable and start the logrotate timer are called.
    """

    def side_effect(*args, **kwargs):
        """Mock side effect function that returns non-zero exit code.

        Args:
            args: Placeholder for positional arguments for lxd exec command.
            kwargs: Placeholder for keyword arguments for lxd exec command.

        Returns:
            A tuple of return value and exit code.
        """
        if "is-active" in args[0]:
            return "", 1
        return "", 0

    lxd_exec_command.side_effect = side_effect

    metrics.setup_logrotate()

    assert (
        call(["/usr/bin/systemctl", "enable", "logrotate.timer"], check_exit=True)
        in lxd_exec_command.mock_calls
    )
    assert (
        call(["/usr/bin/systemctl", "start", "logrotate.timer"], check_exit=True)
        in lxd_exec_command.mock_calls
    )


def test_setup_logrotate_raises_error(lxd_exec_command: MagicMock):
    """
    arrange: Mock execute command to raise a SubprocessError.
    act: Setup logrotate.
    assert: The expected error is raised.
    """
    lxd_exec_command.side_effect = SubprocessError(
        cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr"
    )

    with pytest.raises(LogrotateSetupError):
        metrics.setup_logrotate()
