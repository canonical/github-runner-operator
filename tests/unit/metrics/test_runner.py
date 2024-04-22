# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import secrets
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import shared_fs
from errors import DeleteMetricsStorageError, IssueMetricEventError
from github_type import JobConclusion
from metrics import events as metric_events, type as metrics_type, runner as runner_metrics
from metrics.events import RunnerStart, RunnerStop
from metrics.runner import (
    RUNNER_INSTALLED_TS_FILE_NAME,
    PostJobMetrics,
    PreJobMetrics,
    RunnerMetrics,
)
from metrics.storage import MetricsStorage


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("metrics.events.issue_event", issue_event_mock)
    return issue_event_mock


@pytest.fixture(name="runner_fs_base")
def runner_fs_base_fixture(tmp_path: Path) -> Path:
    """Create a runner filesystem base."""
    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir(exist_ok=True)
    return runner_fs_base


def _create_metrics_data(runner_name: str) -> RunnerMetrics:
    """Create a RunnerMetrics object that is suitable for most tests.

    Args:
        runner_name: The test runner name.

    Returns:
        Test metrics data.
    """
    return RunnerMetrics(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=1,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="org1/repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status=runner_metrics.PostJobStatus.NORMAL),
        runner_name=runner_name,
    )


def _create_runner_fs_base(tmp_path: Path):
    """Create a runner filesystem base.

    Args:
        tmp_path: The temporary path to create test runner filesystem under.

    Returns:
        The runner filesystem temporary path.
    """
    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir(exist_ok=True)
    return runner_fs_base


def _create_runner_files(
    runner_fs_base: Path,
    runner_name: str,
    pre_job_data: str | bytes | None,
    post_job_data: str | bytes | None,
    installed_timestamp: str | bytes | None,
) -> MetricsStorage:
    """Create runner files inside shared fs.

    If the data is bytes, the file is written as binary, otherwise as text.
    If data is None, it is not written.

    Args:
        runner_fs_base: The base path of the shared fs.
        runner_name: The runner name.
        pre_job_data: The pre-job metrics data.
        post_job_data: The post-job metrics data.
        installed_timestamp: The installed timestamp.

    Returns:
        A SharedFilesystem instance.
    """
    runner_fs = runner_fs_base / runner_name
    runner_fs.mkdir()
    if pre_job_data:
        if isinstance(pre_job_data, bytes):
            runner_fs.joinpath(runner_metrics.PRE_JOB_METRICS_FILE_NAME).write_bytes(pre_job_data)
        else:
            runner_fs.joinpath(runner_metrics.PRE_JOB_METRICS_FILE_NAME).write_text(
                pre_job_data, encoding="utf-8"
            )

    if post_job_data:
        if isinstance(post_job_data, bytes):
            runner_fs.joinpath(runner_metrics.POST_JOB_METRICS_FILE_NAME).write_bytes(
                post_job_data
            )
        else:
            runner_fs.joinpath(runner_metrics.POST_JOB_METRICS_FILE_NAME).write_text(
                post_job_data, encoding="utf-8"
            )

    if installed_timestamp:
        if isinstance(installed_timestamp, bytes):
            runner_fs.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).write_bytes(installed_timestamp)
        else:
            runner_fs.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).write_text(
                installed_timestamp, encoding="utf-8"
            )
    return MetricsStorage(path=runner_fs, runner_name=runner_name)


def test_extract(runner_fs_base: Path):
    """
    arrange: \
        1. A runner with all metrics inside shared fs. \
        2. A runner with only pre-job metrics inside shared fs. \
        3. A runner with no metrics except installed_timestamp inside shared fs.
    act: Call extract
    assert: All shared filesystems are removed and for runners
        1. + 2. metrics are extracted
        3. no metrics are extracted
    """
    runner_all_metrics_name = secrets.token_hex(16)
    runner_all_metrics = _create_metrics_data(runner_all_metrics_name)
    runner_wihout_post_job_name = secrets.token_hex(16)
    runner_without_post_job_metrics = runner_all_metrics.copy()
    runner_without_post_job_metrics.post_job = None
    runner_without_post_job_metrics.runner_name = runner_wihout_post_job_name

    # 1. Runner has all metrics inside shared fs
    runner1_fs = _create_runner_files(
        runner_fs_base,
        runner_all_metrics_name,
        runner_all_metrics.pre_job.json(),
        runner_all_metrics.post_job.json(),
        str(runner_all_metrics.installed_timestamp),
    )

    # 2. Runner has only pre-job metrics inside shared fs
    runner2_fs = _create_runner_files(
        runner_fs_base,
        runner_wihout_post_job_name,
        runner_without_post_job_metrics.pre_job.json(),
        None,
        str(runner_without_post_job_metrics.installed_timestamp),
    )

    # 3. Runner has no metrics except installed_timestamp inside shared fs
    runner3_fs = _create_runner_files(runner_fs_base, secrets.token_hex(16), None, None, "5")

    metrics_storage_manager = MagicMock()
    metrics_storage_manager.list_all.return_value = [runner1_fs, runner2_fs, runner3_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )

    assert extracted_metrics == [
        runner_all_metrics,
        runner_without_post_job_metrics,
    ]
    metrics_storage_manager.delete.assert_has_calls(
        [
            ((runner1_fs.runner_name,),),
            ((runner2_fs.runner_name,),),
            ((runner3_fs.runner_name,),),
        ]
    )


def test_extract_ignores_runners(runner_fs_base: Path):
    """
    arrange: Runners with metrics.
    act: Call extract with some runners on ignore list.
    expect: The ignored runners are not processed.
    """
    runner_metrics_data = []

    runner_filesystems = []
    for i in range(5):
        runner_name = secrets.token_hex(16)
        data = _create_metrics_data(runner_name)
        data.pre_job.workflow = f"workflow{i}"
        runner_metrics_data.append(data)
        runner_fs = _create_runner_files(
            runner_fs_base,
            runner_name,
            data.pre_job.json(),
            data.post_job.json(),
            str(data.installed_timestamp),
        )
        runner_filesystems.append(runner_fs)

    metrics_storage_manager = MagicMock()
    metrics_storage_manager.list_all.return_value = runner_filesystems

    ignore_runners = {runner_filesystems[0].runner_name, runner_filesystems[2].runner_name}

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=ignore_runners
        )
    )

    assert extracted_metrics == runner_metrics_data[1:2] + runner_metrics_data[3:]


def test_extract_corrupt_data(runner_fs_base: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: \
        1. A runner with non-compliant pre-job metrics inside shared fs. \
        2. A runner with non-json post-job metrics inside shared fs. \
        3. A runner with json array post-job metrics inside shared fs. \
        4. A runner with no real timestamp in installed_timestamp file inside shared fs.
    act: Call extract.
    assert: No metrics are extracted is issued and shared filesystems are quarantined in all cases.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name=runner_name)

    # 1. Runner has noncompliant pre-job metrics inside shared fs
    invalid_pre_job_data = runner_metrics_data.pre_job.copy(update={"timestamp": -1})
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        invalid_pre_job_data.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager = MagicMock()
    metrics_storage_manager.list_all.return_value = [runner_fs]
    move_to_quarantine_mock = MagicMock()
    monkeypatch.setattr(runner_metrics, "move_to_quarantine", move_to_quarantine_mock)

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )

    assert not extracted_metrics
    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)

    # 2. Runner has non-json post-job metrics inside shared fs
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name=runner_name)

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        b"\x00",
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )
    assert not extracted_metrics
    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)

    # 3. Runner has json post-job metrics but a json array (not object) inside shared fs.
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name=runner_name)

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        json.dumps([runner_metrics_data.post_job.dict()]),
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )
    assert not extracted_metrics
    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)

    # 4. Runner has not a timestamp in installed_timestamp file inside shared fs
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name=runner_name)

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        b"\x00",
    )
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )
    assert not extracted_metrics

    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)


def test_extract_raises_error_for_too_large_files(
    runner_fs_base: Path, issue_event_mock: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Runners with too large metric and timestamp files.
    act: Call extract.
    assert: No metrics are extracted and shared filesystems is quarantined.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)

    # 1. Runner has a pre-job metrics file that is too large
    invalid_pre_job_data = runner_metrics_data.pre_job.copy(
        update={"workflow": "a" * runner_metrics.FILE_SIZE_BYTES_LIMIT + "b"}
    )

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        invalid_pre_job_data.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager = MagicMock()

    metrics_storage_manager.list_all.return_value = [runner_fs]

    move_to_quarantine_mock = MagicMock()
    monkeypatch.setattr(runner_metrics, "move_to_quarantine", move_to_quarantine_mock)

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )
    assert not extracted_metrics

    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)

    # 2. Runner has a post-job metrics file that is too large
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)
    invalid_post_job_data = runner_metrics_data.post_job.copy(
        update={"status": "a" * runner_metrics.FILE_SIZE_BYTES_LIMIT + "b"}
    )
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        invalid_post_job_data.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )

    assert not extracted_metrics

    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)


    # 3. Runner has an installed_timestamp file that is too large
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)

    invalid_ts = "1" * (runner_metrics.FILE_SIZE_BYTES_LIMIT + 1)

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        invalid_ts,
    )
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )

    assert not extracted_metrics
    move_to_quarantine_mock.assert_any_call(metrics_storage_manager, runner_fs.runner_name)


def test_extract_ignores_filesystems_without_ts(runner_fs_base: Path):
    """
    arrange: A runner without installed_timestamp file inside shared fs.
    act: Call extract.
    assert: No metrics are extracted and shared filesystem is removed.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = RunnerMetrics.construct(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=1,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="org1/repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status=runner_metrics.PostJobStatus.NORMAL),
        runner_name=runner_name,
    )

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_name,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        None,
    )
    metrics_storage_manager = MagicMock()
    metrics_storage_manager.list_all.return_value = [runner_fs]

    extracted_metrics = list(
        runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
        )
    )
    assert not extracted_metrics
    metrics_storage_manager.delete.assert_called_once_with(runner_fs.runner_name)


def test_extract_ignores_failure_on_shared_fs_cleanup(
    runner_fs_base: Path,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: Mock the shared_fs.delete to raise an exception.
    act: Call extract.
    assert: The metric is extracted and the exception is caught and logged.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.runner_name,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    metrics_storage_manager = MagicMock()

    metrics_storage_manager.list_all.return_value = [runner_fs]

    metrics_storage_manager.delete.side_effect = DeleteMetricsStorageError(
        "Failed to delete shared filesystem"
    )

    extracted_metrics = runner_metrics.extract(
        metrics_storage_manager=metrics_storage_manager, ignore_runners=set()
    )
    assert list(extracted_metrics) == [runner_metrics_data]

    assert "Failed to delete shared filesystem" in caplog.text


def test_issue_events(issue_event_mock: MagicMock):
    """
    arrange: A runner with all metrics.
    act: Call issue_events.
    assert: RunnerStart and RunnerStop metrics are issued.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert issued_metrics == {metric_events.RunnerStart, metric_events.RunnerStop}
    issue_event_mock.assert_has_calls(
        [
            # 1. Runner
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


def test_issue_events_no_post_job_metrics(issue_event_mock: MagicMock):
    """
    arrange: A runner without  post-job metrics.
    act: Call issue_events.
    assert: Only RunnerStart metric is issued.
    """
    runner_name = secrets.token_hex(16)
    runner_metrics_data = _create_metrics_data(runner_name)
    runner_metrics_data.post_job = None
    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert issued_metrics == {metric_events.RunnerStart}

    issue_event_mock.assert_called_once_with(
        RunnerStart(
            timestamp=runner_metrics_data.pre_job.timestamp,
            flavor=flavor,
            workflow=runner_metrics_data.pre_job.workflow,
            repo=runner_metrics_data.pre_job.repository,
            github_event=runner_metrics_data.pre_job.event,
            idle=runner_metrics_data.pre_job.timestamp - runner_metrics_data.installed_timestamp,
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
    runner_name = secrets.token_hex(16)
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
