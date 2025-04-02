#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import os
import secrets
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from github_runner_manager.configuration import UserInfo
from github_runner_manager.reactive.process_manager import (
    PIDS_COMMAND_LINE,
    PYTHON_BIN,
    REACTIVE_RUNNER_SCRIPT_MODULE,
    ReactiveRunnerError,
    reconcile,
)
from github_runner_manager.reactive.types_ import QueueConfig, ReactiveProcessConfig
from github_runner_manager.utilities import secure_run_subprocess

EXAMPLE_MQ_URI = "http://example.com"


@pytest.fixture(name="log_dir", autouse=True)
def log_dir_path_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return the path to the log file."""
    log_file_path = tmp_path / "logs"
    monkeypatch.setattr(
        "github_runner_manager.reactive.process_manager.REACTIVE_RUNNER_LOG_DIR", log_file_path
    )
    monkeypatch.setattr("shutil.chown", lambda *args, **kwargs: None)
    return log_file_path


@pytest.fixture(name="secure_run_subprocess_mock")
def secure_run_subprocess_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the ps command."""
    secure_run_subprocess_mock = MagicMock(spec=secure_run_subprocess)
    monkeypatch.setattr(
        "github_runner_manager.reactive.process_manager.secure_run_subprocess",
        secure_run_subprocess_mock,
    )
    return secure_run_subprocess_mock


@pytest.fixture(name="os_kill_mock", autouse=True)
def os_kill_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the os.kill function."""
    os_kill_mock = MagicMock(spec=os.kill)
    monkeypatch.setattr("os.kill", os_kill_mock)
    return os_kill_mock


@pytest.fixture(name="subprocess_popen_mock")
def subprocess_popen_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the subprocess.Popen function."""
    popen_result = MagicMock(spec=subprocess.Popen, pid=1234, returncode=0)
    subprocess_popen_mock = MagicMock(
        spec=subprocess.Popen,
        return_value=popen_result,
    )
    monkeypatch.setattr("subprocess.Popen", subprocess_popen_mock)
    return subprocess_popen_mock


@pytest.fixture(name="reactive_process_config")
def reactive_process_config_fixture() -> ReactiveProcessConfig:
    """Return a ReactiveProcessConfig object."""
    queue_name = secrets.token_hex(16)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    queue_config = QueueConfig.construct(mongodb_uri=EXAMPLE_MQ_URI, queue_name=queue_name)
    return ReactiveProcessConfig.construct(queue=queue_config)


def test_reconcile_spawns_runners(
    secure_run_subprocess_mock: MagicMock,
    subprocess_popen_mock: MagicMock,
    log_dir: Path,
    reactive_process_config: ReactiveProcessConfig,
    user_info: UserInfo,
):
    """
    arrange: Mock that two reactive runner processes are active.
    act: Call reconcile with a quantity of 5.
    assert: Three runners are spawned. Log file is setup.
    """
    _arrange_reactive_processes(secure_run_subprocess_mock, count=2)

    delta = reconcile(5, reactive_process_config=reactive_process_config, user=user_info)

    assert delta == 3
    assert subprocess_popen_mock.call_count == 3
    assert log_dir.exists()


def test_reconcile_does_not_spawn_runners(
    secure_run_subprocess_mock: MagicMock,
    subprocess_popen_mock: MagicMock,
    reactive_process_config: ReactiveProcessConfig,
    user_info: UserInfo,
):
    """
    arrange: Mock that two reactive runner processes are active.
    act: Call reconcile with a quantity of 2.
    assert: No runners are spawned.
    """
    _arrange_reactive_processes(secure_run_subprocess_mock, count=2)

    delta = reconcile(2, reactive_process_config=reactive_process_config, user=user_info)

    assert delta == 0
    assert subprocess_popen_mock.call_count == 0


def test_reconcile_kills_processes_for_too_many_processes(
    secure_run_subprocess_mock: MagicMock,
    subprocess_popen_mock: MagicMock,
    os_kill_mock: MagicMock,
    reactive_process_config: ReactiveProcessConfig,
    user_info: UserInfo,
):
    """
    arrange: Mock that 3 reactive runner processes are active.
    act: Call reconcile with a quantity of 1.
    assert: 2 processes are killed.
    """
    _arrange_reactive_processes(secure_run_subprocess_mock, count=3)
    delta = reconcile(1, reactive_process_config=reactive_process_config, user=user_info)

    assert delta == -2
    assert subprocess_popen_mock.call_count == 0
    assert os_kill_mock.call_count == 2


def test_reconcile_ignore_process_not_found_on_kill(
    secure_run_subprocess_mock: MagicMock,
    subprocess_popen_mock: MagicMock,
    os_kill_mock: MagicMock,
    reactive_process_config: ReactiveProcessConfig,
    user_info: UserInfo,
):
    """
    arrange: Mock 3 reactive processes and os.kill to fail once with a ProcessLookupError.
    act: Call reconcile with a quantity of 1.
    assert: The returned delta is still -2.
    """
    _arrange_reactive_processes(secure_run_subprocess_mock, count=3)
    os_kill_mock.side_effect = [None, ProcessLookupError]
    delta = reconcile(1, reactive_process_config=reactive_process_config, user=user_info)

    assert delta == -2
    assert subprocess_popen_mock.call_count == 0
    assert os_kill_mock.call_count == 2


def test_reconcile_raises_reactive_runner_error_on_ps_failure(
    secure_run_subprocess_mock: MagicMock,
    reactive_process_config: ReactiveProcessConfig,
    user_info: UserInfo,
):
    """
    arrange: Mock that the ps command fails.
    act: Call reconcile with a quantity of 1.
    assert: A ReactiveRunnerError is raised.
    """
    secure_run_subprocess_mock.return_value = CompletedProcess(
        args=PIDS_COMMAND_LINE,
        returncode=1,
        stdout=b"",
        stderr=b"error",
    )

    with pytest.raises(ReactiveRunnerError) as err:
        reconcile(1, reactive_process_config=reactive_process_config, user=user_info)

    assert "Failed to get list of processes" in str(err.value)


def _arrange_reactive_processes(secure_run_subprocess_mock: MagicMock, count: int):
    """Mock reactive runner processes are active.

    Args:
        secure_run_subprocess_mock: The mock to use for the ps command.
        count: The number of processes.
    """
    process_cmds_before = "\n".join(
        [f"{PYTHON_BIN} -m {REACTIVE_RUNNER_SCRIPT_MODULE}\t{i}" for i in range(count)]
    )

    secure_run_subprocess_mock.return_value = CompletedProcess(
        args=PIDS_COMMAND_LINE,
        returncode=0,
        stdout=f"CMD\n{process_cmds_before}".encode("utf-8"),
        stderr=b"",
    )
