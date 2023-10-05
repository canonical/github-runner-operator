#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path

from metrics import RunnerInstalled, issue_event

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
