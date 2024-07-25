#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path

from metrics import events

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


def test_issue_events_logs_events(tmp_path: Path):
    """
    arrange: Change path of the events log.
    act: Issue a metric event.
    assert: The expected metric log is created.
    """
    event = events.RunnerInstalled(timestamp=123, flavor="small", duration=456)

    events.issue_event(event)

    assert json.loads(events.METRICS_LOG_PATH.read_text()) == {
        "event": "runner_installed",
        "timestamp": 123,
        "flavor": "small",
        "duration": 456,
    }


def test_issue_events_exclude_none_values(tmp_path: Path):
    """
    arrange: Change path of the events log.
    act: Issue a metric event with a None value.
    assert: The expected metric log without the None value is created.
    """
    event = events.RunnerStop(
        timestamp=123,
        flavor="small",
        workflow="workflow",
        repo="repo",
        github_event="github_event",
        status="status",
        status_info=None,
        job_duration=456,
    )

    events.issue_event(event)

    assert json.loads(events.METRICS_LOG_PATH.read_text()) == {
        "event": "runner_stop",
        "timestamp": 123,
        "flavor": "small",
        "workflow": "workflow",
        "repo": "repo",
        "github_event": "github_event",
        "status": "status",
        "job_duration": 456,
    }
