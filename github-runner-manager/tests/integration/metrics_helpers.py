# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for app-level integration metrics assertions."""

import json
import time
from pathlib import Path
from typing import Any

from github.Repository import Repository

from github_runner_manager.manager.vm_manager import PostJobStatus
from github_runner_manager.types_.github import JobConclusion

TEST_WORKFLOW_NAMES = [
    "Workflow Dispatch Tests",
    "Workflow Dispatch Crash Tests",
    "Workflow Dispatch Failure Tests 2a34f8b1-41e4-4bcb-9bbf-7a74e6c482f7",
]


def _assert_non_negative_number(metric: dict[str, Any], key: str) -> None:
    """Assert event key exists and contains a non-negative numeric value."""
    assert key in metric, f"Missing metric field: {key}"
    value = metric[key]
    assert isinstance(value, (int, float)), f"Metric field {key} is not numeric: {value!r}"
    assert value >= 0, f"Metric field {key} is negative: {value!r}"


def clear_metrics_log(metrics_log_path: Path) -> None:
    """Delete metrics log file to reset test state."""
    metrics_log_path.unlink(missing_ok=True)


def get_metrics_events(metrics_log_path: Path) -> list[dict[str, Any]]:
    """Return metrics events from the log file."""
    if not metrics_log_path.exists():
        return []
    lines = metrics_log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def wait_for_events(
    metrics_log_path: Path,
    expected_events: set[str],
    timeout: int = 10 * 60,
    interval: int = 10,
) -> list[dict[str, Any]]:
    """Wait until all expected event names are present in the metrics log."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = get_metrics_events(metrics_log_path)
        emitted = {event.get("event") for event in events}
        if expected_events <= emitted:
            return events
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for metrics events: {sorted(expected_events)}")


def assert_events_after_reconciliation(
    events: list[dict[str, Any]],
    flavor: str,
    github_repository: Repository,
    post_job_status: PostJobStatus,
) -> None:
    """Assert runner-start/stop/reconciliation metrics for a completed test flow."""
    emitted = {event.get("event") for event in events}
    assert {
        "runner_start",
        "runner_stop",
        "reconciliation",
    } <= emitted, "Not all metrics events were logged"

    for metric in events:
        if metric.get("event") == "runner_start":
            assert metric.get("flavor") == flavor
            assert metric.get("workflow") in TEST_WORKFLOW_NAMES
            assert metric.get("repo") == github_repository.full_name
            assert metric.get("github_event") == "workflow_dispatch"
            _assert_non_negative_number(metric, "idle")
            _assert_non_negative_number(metric, "queue_duration")

        if metric.get("event") == "runner_stop":
            assert metric.get("flavor") == flavor
            assert metric.get("workflow") in TEST_WORKFLOW_NAMES
            assert metric.get("repo") == github_repository.full_name
            assert metric.get("github_event") == "workflow_dispatch"
            assert metric.get("status") == post_job_status
            if post_job_status == PostJobStatus.ABNORMAL:
                assert metric.get("status_info", {}).get("code", 0) != 0
                assert metric.get("job_conclusion") in [None, JobConclusion.CANCELLED]
            else:
                assert "status_info" not in metric
                assert metric.get("job_conclusion") == JobConclusion.SUCCESS
            _assert_non_negative_number(metric, "job_duration")

        if metric.get("event") == "reconciliation":
            assert metric.get("flavor") == flavor
            _assert_non_negative_number(metric, "duration")
            assert metric.get("crashed_runners") == 0
            _assert_non_negative_number(metric, "idle_runners")
            _assert_non_negative_number(metric, "active_runners")
            _assert_non_negative_number(metric, "expected_runners")


def wait_for_runner_to_be_marked_offline(
    github_repository: Repository,
    runner_name: str,
    timeout: int = 30 * 60,
    interval: int = 60,
) -> None:
    """Wait for a runner to become offline or disappear from GitHub."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for runner in github_repository.get_self_hosted_runners():
            if runner.name == runner_name:
                if runner.status == "online":
                    time.sleep(interval)
                    break
        else:
            return
    raise TimeoutError(f"Timeout while waiting for runner {runner_name} to be marked offline")
