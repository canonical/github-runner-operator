#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

import shared_fs


@pytest.fixture(autouse=True, name="filesystems_paths")
def filesystems_paths_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> Path:
    """
    Mock the hardcoded promtail paths.
    """
    fs_path = tmp_path / "runner-fs"
    monkeypatch.setattr("shared_fs.FILESYSTEM_PATH", fs_path)
    return fs_path


@pytest.fixture(autouse=True, name="exc_cmd_mock")
def exc_command_fixture(monkeypatch: MonkeyPatch) -> Mock:
    """Mock the execution of a command."""
    exc_cmd_mock = Mock()
    monkeypatch.setattr("shared_fs.execute_command", exc_cmd_mock)
    return exc_cmd_mock


def test_create_shared_filesystem(filesystems_paths: Path):
    """
    arrange: Given a runner name and a path for the filesystems and a mocked execute_command
    act: Call create
    assert: The shared filesystem path is created
    """
    runner_name = secrets.token_hex(16)

    fs = shared_fs.create(runner_name)

    assert fs.path.exists()


def test_create_raises_exception(exc_cmd_mock):
    """
    arrange: Given a runner name and a mocked execute_command which raises an exception
    act: Call create
    assert: The exception is raised
    """
    runner_name = secrets.token_hex(16)
    exc_cmd_mock.side_effect = Exception()

    with pytest.raises(Exception):
        shared_fs.create(runner_name)


def test_get_shared_filesystem(filesystems_paths: Path):
    """
    arrange: Given a runner name and a path for the filesystems and a mocked execute_command
    act: Call get
    assert: A shared filesystem object is returned
    """
    runner_name = secrets.token_hex(16)

    fs = shared_fs.get(runner_name)

    assert isinstance(fs, shared_fs.SharedFilesystem)
    assert fs.runner_name == runner_name
