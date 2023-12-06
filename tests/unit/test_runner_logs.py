#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import runner_logs
from runner_logs import get_crashed_runner_logs


@pytest.fixture(name="log_dir_base_path")
def log_dir_base_path_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the log directory path and return it."""
    log_dir_base_path = tmp_path / "log_dir"
    monkeypatch.setattr(runner_logs, "CRASHED_RUNNER_LOGS_DIR_PATH", log_dir_base_path)
    return log_dir_base_path


def test_get_crashed_runner_logs(log_dir_base_path: Path):
    """
    arrange: Mock the Runner instance and the base log directory path
    act: Get the logs of the crashed runner
    assert: The expected log directory is created and logs are pulled
    """
    runner = MagicMock()
    runner.config.name = "test-runner"
    runner.instance.files.pull_file = MagicMock()

    get_crashed_runner_logs(runner)

    assert log_dir_base_path.exists()

    log_dir_path = log_dir_base_path / "test-runner"
    log_dir_base_path.exists()

    runner.instance.files.pull_file.assert_has_calls(
        [
            call(str(runner_logs.DIAG_DIR_PATH), str(log_dir_path), is_dir=True),
            call(str(runner_logs.SYSLOG_PATH), str(log_dir_path)),
        ]
    )


def test_remove_outdated_crashed_runner_logs(
    log_dir_base_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock the base log directory path
    act: Remove the logs of the crashed runner
    assert: The expected logs are removed
    """
    monkeypatch.setattr(runner_logs, "SEVEN_DAYS_IN_SECONDS", 0)

    log_dir_path = log_dir_base_path / "test-runner"
    log_dir_path.mkdir(parents=True)

    runner_logs.remove_outdated_crashed_runner_logs()

    assert not log_dir_path.exists()
