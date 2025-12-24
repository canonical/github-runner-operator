"""Unit tests for github_runner_manager.metrics.events."""

#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from pathlib import Path

import pytest

from github_runner_manager.metrics import events

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


@pytest.fixture(autouse=True, name="patch_metrics_path")
def patch_metrics_path_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Patch metrics path derivation to use a temp file."""
    metrics_log_path = Path(tmp_path / "metrics.log")
    monkeypatch.setattr(
        "github_runner_manager.metrics.events.get_metrics_log_path",
        lambda base_dir: metrics_log_path,
    )


def test_issue_events_logs_events(tmp_path: Path):
    """Issuing an event writes expected JSON to metrics log."""
    event = events.RunnerInstalled(timestamp=123, flavor="small", duration=456)

    events.issue_event(event, base_dir=str(tmp_path))

    assert json.loads((tmp_path / "metrics.log").read_text()) == {
        "event": "runner_installed",
        "timestamp": 123,
        "flavor": "small",
        "duration": 456,
    }


def test_issue_events_exclude_none_values(tmp_path: Path):
    """None fields are excluded from logged event JSON."""
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

    events.issue_event(event, base_dir=str(tmp_path))

    assert json.loads((tmp_path / "metrics.log").read_text()) == {
        "event": "runner_stop",
        "timestamp": 123,
        "flavor": "small",
        "workflow": "workflow",
        "repo": "repo",
        "github_event": "github_event",
        "status": "status",
        "job_duration": 456,
    }
