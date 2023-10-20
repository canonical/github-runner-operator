#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import secrets
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from _pytest.monkeypatch import MonkeyPatch

import errors
import runner_metrics
import shared_fs
from metrics import RunnerStart
from runner_metrics import (
    RUNNER_INSTALLED_TS_FILE_NAME,
    PostJobMetrics,
    PreJobMetrics,
    RunnerMetrics,
)


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("metrics.issue_event", issue_event_mock)
    return issue_event_mock


@pytest.fixture(autouse=True, name="shared_fs_mock")
def shared_fs_mock_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    shared_fs_mock = MagicMock(spec=shared_fs)
    monkeypatch.setattr("runner_metrics.shared_fs", shared_fs_mock)
    return shared_fs_mock


def _create_runner_files(
    runner_fs_base: Path,
    pre_job_data: str | bytes | None,
    post_job_data: str | bytes | None,
    installed_timestamp: str | bytes | None,
) -> shared_fs.SharedFilesystem:
    """Create runner files inside shared fs.

    If the data is bytes, the file is written as binary, otherwise as text.
    If data is None, it is not written.

    Args:
        runner_fs_base: The base path of the shared fs.
        pre_job_data: The pre-job metrics data.
        post_job_data: The post-job metrics data.
        installed_timestamp: The installed timestamp.
    """
    runner_name = secrets.token_hex(16)
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
    return shared_fs.SharedFilesystem(path=runner_fs, runner_name=runner_name)


def test_extract(shared_fs_mock: MagicMock, issue_event_mock: MagicMock, tmp_path: Path):
    """
    arrange:
        1. A runner with all metrics inside shared fs
        2. A runner with only pre-job metrics inside shared fs
        3. A runner with no metrics except installed_timestamp inside shared fs
    act: Call extract
    assert: For runners 1 & 2 RunnerStart events are issued and all shared filesystems are removed.
    """
    runner_with_all_metrics = RunnerMetrics(
        installed_timestamp=1696427232.2253454,
        pre_job=PreJobMetrics(
            timestamp=1796427232.2253454,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )
    runner_without_post_job_metrics = RunnerMetrics(
        installed_timestamp=4,
        pre_job=PreJobMetrics(
            timestamp=5,
            workflow="workflow2",
            workflow_run_id="workflow_run_id2",
            repository="repository2",
            event="workflow_dispatch",
        ),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    # 1. Runner has all metrics inside shared fs
    runner1_fs = _create_runner_files(
        runner_fs_base,
        runner_with_all_metrics.pre_job.json(),
        runner_with_all_metrics.post_job.json(),
        str(runner_with_all_metrics.installed_timestamp),
    )

    # 2. Runner has only pre-job metrics inside shared fs
    runner2_fs = _create_runner_files(
        runner_fs_base,
        runner_without_post_job_metrics.pre_job.json(),
        None,
        str(runner_without_post_job_metrics.installed_timestamp),
    )

    # 3. Runner has no metrics except installed_timestamp inside shared fs
    runner3_fs = _create_runner_files(runner_fs_base, None, None, "5")

    shared_fs_mock.list_all.return_value = [runner1_fs, runner2_fs, runner3_fs]

    flavor = secrets.token_hex(16)
    runner_metrics.extract(flavor, set())

    issue_event_mock.assert_has_calls(
        [
            call(
                RunnerStart(
                    timestamp=runner_with_all_metrics.pre_job.timestamp,
                    flavor=flavor,
                    workflow=runner_with_all_metrics.pre_job.workflow,
                    repo=runner_with_all_metrics.pre_job.repository,
                    github_event=runner_with_all_metrics.pre_job.event,
                    # Ignore line break before binary operator
                    idle=runner_with_all_metrics.pre_job.timestamp
                    - runner_with_all_metrics.installed_timestamp,  # noqa: W503
                )
            ),
            call(
                RunnerStart(
                    timestamp=runner_without_post_job_metrics.pre_job.timestamp,
                    flavor=flavor,
                    workflow=runner_without_post_job_metrics.pre_job.workflow,
                    repo=runner_without_post_job_metrics.pre_job.repository,
                    github_event=runner_without_post_job_metrics.pre_job.event,
                    # Ignore line break before binary operator
                    idle=runner_without_post_job_metrics.pre_job.timestamp
                    - runner_without_post_job_metrics.installed_timestamp,  # noqa: W503
                ),
            ),
        ]
    )

    shared_fs_mock.delete.assert_has_calls(
        [
            ((runner1_fs.runner_name,),),
            ((runner2_fs.runner_name,),),
            ((runner3_fs.runner_name,),),
        ]
    )


def test_extract_ignores_runners(
    shared_fs_mock: MagicMock, issue_event_mock: MagicMock, tmp_path: Path
):
    """
    arrange: Runners with metrics.
    act: Call extract with some runners on ignore list
    expect: The ignored runners are not processed.
    """
    runner_metrics_data = RunnerMetrics(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=2.3,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    runner_filesystems = []
    for i in range(5):
        data = runner_metrics_data.copy()
        data.pre_job.workflow = f"workflow{i}"
        runner_fs = _create_runner_files(
            runner_fs_base,
            runner_metrics_data.pre_job.json(),
            runner_metrics_data.post_job.json(),
            str(runner_metrics_data.installed_timestamp),
        )
        runner_filesystems.append(runner_fs)

    shared_fs_mock.list_all.return_value = runner_filesystems

    flavor = secrets.token_hex(16)
    runner_metrics.extract(
        flavor, {runner_filesystems[0].runner_name, runner_filesystems[2].runner_name}
    )

    for i in (0, 2):
        assert (
            call(
                RunnerStart(
                    timestamp=runner_metrics_data.pre_job.timestamp,
                    flavor=flavor,
                    workflow=f"workflow{i}",
                    repo=runner_metrics_data.pre_job.repository,
                    github_event=runner_metrics_data.pre_job.event,
                    # Ignore line break before binary operator
                    idle=runner_metrics_data.pre_job.timestamp
                    - runner_metrics_data.installed_timestamp,  # noqa: W503
                )
            )
            not in issue_event_mock.mock_calls
        )
        assert call((runner_filesystems[i].runner_name,)) not in shared_fs_mock.delete.mock_calls


def test_extract_raises_errors(tmp_path: Path, shared_fs_mock: MagicMock):
    """
    arrange:
        1. A runner with non-compliant pre-job metrics inside shared fs
        2. A runner with non-json post-job metrics inside shared fs
        3. A runner with json array post-job metrics inside shared fs
        4. A runner with no real timestamp in installed_timestamp file inside shared fs
    act: Call extract
    assert: CorruptMetricDataError raised in all cases.
    """
    runner_metrics_data = RunnerMetrics(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=1,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    # 1. Runner has noncompliant pre-job metrics inside shared fs
    invalid_pre_job_data = runner_metrics_data.pre_job.copy(update={"timestamp": -1})
    runner_fs = _create_runner_files(
        runner_fs_base,
        invalid_pre_job_data.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    flavor = secrets.token_hex(16)

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())

    # 2. Runner has non-json post-job metrics inside shared fs
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        b"\x00",
        str(runner_metrics_data.installed_timestamp),
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())

    # 3. Runner has json post-job metrics but a json array (not object) inside shared fs.
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        json.dumps([runner_metrics_data.post_job.dict()]),
        str(runner_metrics_data.installed_timestamp),
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())

    # 4. Runner has not a timestamp in installed_timestamp file inside shared fs
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        b"\x00",
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())


def test_extract_raises_error_for_too_large_files(tmp_path: Path, shared_fs_mock: MagicMock):
    """
    arrange: Runners with too large metric and timestamp files.
    act: Call extract.
    assert: CorruptMetricDataError raised  in all cases.
    """
    runner_metrics_data = RunnerMetrics(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=1,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    # 1. Runner has a pre-job metrics file that is too large
    invalid_pre_job_data = runner_metrics_data.pre_job.copy(
        update={"workflow": "a" * runner_metrics.FILE_SIZE_BYTES_LIMIT + "b"}
    )

    runner_fs = _create_runner_files(
        runner_fs_base,
        invalid_pre_job_data.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    flavor = secrets.token_hex(16)

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())

    # 2. Runner has a post-job metrics file that is too large
    invalid_post_job_data = runner_metrics_data.post_job.copy(
        update={"status": "a" * runner_metrics.FILE_SIZE_BYTES_LIMIT + "b"}
    )
    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        invalid_post_job_data.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())

    # 3. Runner has an installed_timestamp file that is too large
    invalid_ts = "1" * (runner_metrics.FILE_SIZE_BYTES_LIMIT + 1)

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        invalid_ts,
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())


def test_extract_raises_error_for_unexpected_files(tmp_path: Path, shared_fs_mock: MagicMock):
    """
    arrange: A runner with unexpected files inside shared fs.
    act: Call extract.
    assert: CorruptMetricDataError is raised and shared filesystem is removed.
    """
    runner_metrics_data = RunnerMetrics(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=2.3,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        str(runner_metrics_data.installed_timestamp),
    )
    runner_fs.path.joinpath("unexpected").write_text("unexpected file")
    shared_fs_mock.list_all.return_value = [runner_fs]

    flavor = secrets.token_hex(16)

    with pytest.raises(errors.CorruptMetricDataError):
        runner_metrics.extract(flavor, set())
    shared_fs_mock.delete.assert_called_once_with(runner_fs.runner_name)


def test_extract_ignores_filesystems_without_ts(
    issue_event_mock: MagicMock, tmp_path: Path, shared_fs_mock: MagicMock
):
    """
    arrange: A runner without installed_timestamp file inside shared fs.
    act: Call extract.
    assert: No event is issued and shared filesystem is removed.
    """
    runner_metrics_data = RunnerMetrics.construct(
        installed_timestamp=1,
        pre_job=PreJobMetrics(
            timestamp=1,
            workflow="workflow1",
            workflow_run_id="workflow_run_id1",
            repository="repository1",
            event="push",
        ),
        post_job=PostJobMetrics(timestamp=3, status="status1"),
    )

    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir()

    runner_fs = _create_runner_files(
        runner_fs_base,
        runner_metrics_data.pre_job.json(),
        runner_metrics_data.post_job.json(),
        None,
    )
    shared_fs_mock.list_all.return_value = [runner_fs]

    flavor = secrets.token_hex(16)

    runner_metrics.extract(flavor, set())

    issue_event_mock.assert_not_called()
    shared_fs_mock.delete.assert_called_once_with(runner_fs.runner_name)
