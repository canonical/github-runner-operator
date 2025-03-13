# Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from github_runner_manager.errors import IssueMetricEventError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics import type as metrics_type
from github_runner_manager.metrics.events import RunnerInstalled, RunnerStart, RunnerStop
from github_runner_manager.metrics.runner import (
    PostJobMetrics,
    PreJobMetrics,
    RunnerMetrics,
)
from github_runner_manager.types_.github import JobConclusion


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("github_runner_manager.metrics.events.issue_event", issue_event_mock)
    return issue_event_mock


@pytest.fixture(name="runner_fs_base")
def runner_fs_base_fixture(tmp_path: Path) -> Path:
    """Create a runner filesystem base."""
    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir(exist_ok=True)
    return runner_fs_base


def _create_metrics_data(instance_id: InstanceID) -> RunnerMetrics:
    """Create a RunnerMetrics object that is suitable for most tests.

    Args:
        instance_id: The test runner name.

    Returns:
        Test metrics data.
    """
    return RunnerMetrics(
        installation_start_timestamp=1,
        installed_timestamp=2,
        pre_job=PreJobMetrics(
            timestamp=3,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="org1/repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status=runner_metrics.PostJobStatus.NORMAL),
        instance_id=instance_id,
    )


def test_issue_events(issue_event_mock: MagicMock):
    """
    arrange: A runner with all metrics.
    act: Call issue_events.
    assert: RunnerInstalled, RunnerStart and RunnerStop metrics are issued.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert issued_metrics == {
        metric_events.RunnerInstalled,
        metric_events.RunnerStart,
        metric_events.RunnerStop,
    }
    issue_event_mock.assert_has_calls(
        [
            call(
                RunnerInstalled(
                    timestamp=runner_metrics_data.installed_timestamp,
                    flavor=flavor,
                    duration=runner_metrics_data.installed_timestamp
                    - runner_metrics_data.installation_start_timestamp,
                )
            ),
            call(
                RunnerStart(
                    timestamp=runner_metrics_data.pre_job.timestamp,
                    flavor=flavor,
                    workflow=runner_metrics_data.pre_job.workflow,
                    repo=runner_metrics_data.pre_job.repository,
                    github_event=runner_metrics_data.pre_job.event,
                    idle=runner_metrics_data.pre_job.timestamp
                    - runner_metrics_data.installed_timestamp,
                    queue_duration=job_metrics.queue_duration,
                )
            ),
            call(
                RunnerStop(
                    timestamp=runner_metrics_data.post_job.timestamp,
                    flavor=flavor,
                    workflow=runner_metrics_data.pre_job.workflow,
                    repo=runner_metrics_data.pre_job.repository,
                    github_event=runner_metrics_data.pre_job.event,
                    status=runner_metrics_data.post_job.status,
                    job_duration=runner_metrics_data.post_job.timestamp
                    - runner_metrics_data.pre_job.timestamp,
                    job_conclusion=job_metrics.conclusion,
                )
            ),
        ]
    )


def test_issue_events_pre_job_before_runner_installed(issue_event_mock: MagicMock):
    """
    arrange: A runner with pre-job timestamp smaller than installed timestamp.
    act: Call issue_events.
    assert: RunnerStart metric is issued with idle set to 0.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)
    runner_metrics_data.pre_job.timestamp = 0

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert metric_events.RunnerStart in issued_metrics
    issue_event_mock.assert_has_calls(
        [
            call(
                RunnerStart(
                    timestamp=runner_metrics_data.pre_job.timestamp,
                    flavor=flavor,
                    workflow=runner_metrics_data.pre_job.workflow,
                    repo=runner_metrics_data.pre_job.repository,
                    github_event=runner_metrics_data.pre_job.event,
                    idle=0,
                    queue_duration=job_metrics.queue_duration,
                )
            )
        ]
    )


def test_issue_events_post_job_before_pre_job(issue_event_mock: MagicMock):
    """
    arrange: A runner with post-job timestamp smaller than pre-job timestamps.
    act: Call issue_events.
    assert: job_duration is set to zero.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)
    runner_metrics_data.post_job = PostJobMetrics(
        timestamp=0, status=runner_metrics.PostJobStatus.NORMAL
    )
    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )

    assert metric_events.RunnerStop in issued_metrics
    issue_event_mock.assert_has_calls(
        [
            call(
                RunnerStop(
                    timestamp=runner_metrics_data.post_job.timestamp,
                    flavor=flavor,
                    workflow=runner_metrics_data.pre_job.workflow,
                    repo=runner_metrics_data.pre_job.repository,
                    github_event=runner_metrics_data.pre_job.event,
                    status=runner_metrics_data.post_job.status,
                    job_duration=0,
                    job_conclusion=job_metrics.conclusion,
                )
            ),
        ]
    )


@pytest.mark.parametrize(
    "with_installation_start",
    [
        pytest.param(True, id="with installation start ts"),
        pytest.param(False, id="without installation start ts"),
    ],
)
@pytest.mark.parametrize(
    "with_pre_job, with_post_job",
    [
        pytest.param(True, True, id="with pre_job, with_post_job"),
        pytest.param(True, False, id="with pre_job, without_post_job"),
        pytest.param(False, False, id="without pre_job and post_job"),
    ],
)
def test_issue_events_partial_metrics(
    with_installation_start: bool,
    with_pre_job: bool,
    with_post_job: bool,
    issue_event_mock: MagicMock,
):
    """
    arrange: A runner with partial metrics.
    act: Call issue_events.
    assert: Only the expected metrics are issued.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)
    if not with_installation_start:
        runner_metrics_data.installation_start_timestamp = None
    if not with_pre_job:
        runner_metrics_data.pre_job = None
    if not with_post_job:
        runner_metrics_data.post_job = None
    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )

    expected_metrics = {metric_events.RunnerInstalled} if with_installation_start else set()
    expected_metrics |= {metric_events.RunnerStart} if with_pre_job else set()
    expected_metrics |= {metric_events.RunnerStop} if with_post_job else set()
    assert issued_metrics == expected_metrics

    if with_installation_start:
        issue_event_mock.assert_any_call(
            RunnerInstalled(
                timestamp=runner_metrics_data.installed_timestamp,
                flavor=flavor,
                duration=runner_metrics_data.installed_timestamp
                - runner_metrics_data.installation_start_timestamp,
            )
        )

    if with_pre_job:
        issue_event_mock.assert_any_call(
            RunnerStart(
                timestamp=runner_metrics_data.pre_job.timestamp,
                flavor=flavor,
                workflow=runner_metrics_data.pre_job.workflow,
                repo=runner_metrics_data.pre_job.repository,
                github_event=runner_metrics_data.pre_job.event,
                idle=runner_metrics_data.pre_job.timestamp
                - runner_metrics_data.installed_timestamp,
                queue_duration=job_metrics.queue_duration,
            )
        )

    if with_post_job:
        issue_event_mock.assert_any_call(
            RunnerStart(
                timestamp=runner_metrics_data.pre_job.timestamp,
                flavor=flavor,
                workflow=runner_metrics_data.pre_job.workflow,
                repo=runner_metrics_data.pre_job.repository,
                github_event=runner_metrics_data.pre_job.event,
                idle=runner_metrics_data.pre_job.timestamp
                - runner_metrics_data.installed_timestamp,
                queue_duration=job_metrics.queue_duration,
            )
        )


def test_issue_events_returns_empty_set_on_issue_event_failure(
    issue_event_mock: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: Mock the issue_event_mock to raise an exception on the first call.
    act: Call issue_events.
    assert: No metrics at all are issued. The exception is caught and logged.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)

    issue_event_mock.side_effect = [IssueMetricEventError("Failed to issue metric"), None]

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )

    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert not issued_metrics
    assert "Failed to issue metric" in caplog.text


def test_issue_events_post_job_but_no_pre_job(
    issue_event_mock: MagicMock,
):
    """
    arrange: A runner with post-job metrics but no pre-job metrics.
    act: Call issue_events.
    assert: Only RunnerInstalled is issued.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)
    runner_metrics_data.pre_job = None

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )

    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert issued_metrics == {metric_events.RunnerInstalled}
