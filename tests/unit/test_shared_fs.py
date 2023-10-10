#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

import shared_fs


@pytest.fixture(autouse=True, name="filesystem_base_path")
def filesystem_base_path_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> Path:
    """
    Mock the hardcoded filesystem base path.
    """
    fs_path = tmp_path / "runner-fs"
    monkeypatch.setattr("shared_fs.FILESYSTEM_BASE_PATH", fs_path)
    return fs_path


@pytest.fixture(autouse=True, name="exc_cmd_mock")
def exc_command_fixture(monkeypatch: MonkeyPatch) -> Mock:
    """Mock the execution of a command."""
    exc_cmd_mock = Mock()
    monkeypatch.setattr("shared_fs.execute_command", exc_cmd_mock)
    return exc_cmd_mock


def test_create_creates_directory(filesystem_base_path: Path):
    """
    arrange: Given a runner name and a path for the filesystems.
    act: Call create.
    assert: The shared filesystem path is created.
    """
    runner_name = secrets.token_hex(16)

    fs = shared_fs.create(runner_name)

    assert fs.path.exists()
    assert fs.path.is_dir()


def test_create_raises_exception(exc_cmd_mock):
    """
    arrange: Given a runner name and a mocked execute_command which raises an exception.
    act: Call create.
    assert: The exception is raised.
    """
    runner_name = secrets.token_hex(16)
    exc_cmd_mock.side_effect = Exception()

    with pytest.raises(Exception):
        shared_fs.create(runner_name)


def test_list_shared_filesystems(filesystem_base_path: Path):
    """
    arrange: Create shared filesystems for multiple runners.
    act: Call list.
    assert: A generator listing all the shared filesystems is returned.
    """
    runner_names = [secrets.token_hex(16) for _ in range(3)]
    for runner_name in runner_names:
        shared_fs.create(runner_name)

    fs_list = list(shared_fs.list_all())

    assert len(fs_list) == 3
    for fs in fs_list:
        assert isinstance(fs, shared_fs.SharedFilesystem)
        assert fs.runner_name in runner_names


def test_list_shared_filesystems_empty():
    """
    arrange: Nothing.
    act: Call list.
    assert: An empty generator is returned.
    """
    fs_list = list(shared_fs.list_all())

    assert len(fs_list) == 0


def test_delete_filesystem():
    """
    arrange: Create a shared filesystem for a runner.
    act: Call delete
    assert: The shared filesystem is deleted.
    """
    runner_name = secrets.token_hex(16)
    shared_fs.create(runner_name)

    shared_fs.delete(runner_name)

    with pytest.raises(shared_fs.NotFoundError):
        shared_fs.get(runner_name)


def test_delete_raises_not_found_error():
    """
    arrange: Nothing.
    act: Call delete.
    assert: A NotFoundError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(shared_fs.NotFoundError):
        shared_fs.delete(runner_name)


def test_get_shared_filesystem():
    """
    arrange: Given a runner name.
    act: Call create and get.
    assert: A shared filesystem object for this runner is returned.
    """
    runner_name = secrets.token_hex(16)

    shared_fs.create(runner_name)
    fs = shared_fs.get(runner_name)

    assert isinstance(fs, shared_fs.SharedFilesystem)
    assert fs.runner_name == runner_name


def test_get_raises_not_found_error():
    """
    arrange: Nothing.
    act: Call get.
    assert: A NotFoundError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(shared_fs.NotFoundError):
        shared_fs.get(runner_name)
