#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
from pathlib import Path

import pytest

from github_runner_manager.metrics import runner_logs


@pytest.fixture(name="log_dir_base_path")
def log_dir_base_path_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the log directory path and return it."""
    log_dir_base_path = tmp_path / "log_dir"
    monkeypatch.setattr(runner_logs, "RUNNER_LOGS_DIR_PATH", log_dir_base_path)
    return log_dir_base_path


def test_remove_outdated_crashed(log_dir_base_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock the base log directory path.
    act: Remove the logs of the runner.
    assert: The expected logs are removed.
    """
    monkeypatch.setattr(runner_logs, "OUTDATED_LOGS_IN_SECONDS", 0)

    log_dir_path = log_dir_base_path / "test-runner"
    log_dir_path.mkdir(parents=True)

    runner_logs.remove_outdated()

    assert not log_dir_path.exists()
