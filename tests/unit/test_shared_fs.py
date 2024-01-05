# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

import errors
import shared_fs
from errors import SubprocessError


@pytest.fixture(autouse=True, name="filesystem_paths")
def filesystem_paths_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """
    Mock the hardcoded filesystem paths.
    """
    fs_path = tmp_path / "runner-fs"
    fs_images_path = tmp_path / "images"
    fs_quarantine_path = tmp_path / "quarantine"
    monkeypatch.setattr("shared_fs.FILESYSTEM_BASE_PATH", fs_path)
    monkeypatch.setattr("shared_fs.FILESYSTEM_IMAGES_PATH", fs_images_path)
    monkeypatch.setattr("shared_fs.FILESYSTEM_QUARANTINE_PATH", fs_quarantine_path)
    return {"base": fs_path, "images": fs_images_path, "quarantine": fs_quarantine_path}


@pytest.fixture(autouse=True, name="exc_cmd_mock")
def exc_command_fixture(monkeypatch: MonkeyPatch) -> Mock:
    """Mock the execution of a command."""
    exc_cmd_mock = Mock()
    monkeypatch.setattr("shared_fs.execute_command", exc_cmd_mock)
    return exc_cmd_mock


def test_create_creates_directory():
    """
    arrange: Given a runner name and a path for the filesystems.
    act: Call create.
    assert: The shared filesystem path is created.
    """
    runner_name = secrets.token_hex(16)

    fs = shared_fs.create(runner_name)

    assert fs.path.exists()
    assert fs.path.is_dir()


def test_create_raises_exception(exc_cmd_mock: MagicMock):
    """
    arrange: Given a runner name and a mocked execute_command which raises an expected exception.
    act: Call create.
    assert: The expected exception is raised.
    """
    runner_name = secrets.token_hex(16)
    exc_cmd_mock.side_effect = SubprocessError(
        cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr"
    )

    with pytest.raises(errors.CreateSharedFilesystemError):
        shared_fs.create(runner_name)


def test_create_raises_exception_if_already_exists():
    """
    arrange: Given a runner name and an already existing shared filesystem.
    act: Call create.
    assert: The expected exception is raised.
    """
    runner_name = secrets.token_hex(16)
    shared_fs.create(runner_name)

    with pytest.raises(errors.CreateSharedFilesystemError):
        shared_fs.create(runner_name)


def test_list_shared_filesystems():
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

    with pytest.raises(errors.SharedFilesystemNotFoundError):
        shared_fs.get(runner_name)


def test_delete_raises_error():
    """
    arrange: Nothing.
    act: Call delete.
    assert: A DeleteSharedFileSystemError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(errors.DeleteSharedFilesystemError):
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
    assert: A SharedFilesystemNotFoundError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(errors.SharedFilesystemNotFoundError):
        shared_fs.get(runner_name)


def test_quarantine(filesystem_paths: dict[str, Path], tmp_path: Path):
    """
    arrange: Create a shared filesystem for a runner with a file in it.
    act: Call quarantine.
    assert: The shared filesystem is moved to the quarantine.
    """
    runner_name = secrets.token_hex(16)
    fs = shared_fs.create(runner_name)
    fs.path.joinpath("test.txt").write_text("foo bar")

    shared_fs.move_to_quarantine(runner_name)

    tarfile_path = filesystem_paths["quarantine"].joinpath(runner_name).with_suffix(".tar.gz")
    assert tarfile_path.exists()
    tarfile.open(tarfile_path).extractall(path=tmp_path)
    assert tmp_path.joinpath(f"{runner_name}/test.txt").exists()
    assert tmp_path.joinpath(f"{runner_name}/test.txt").read_text(encoding="utf-8") == "foo bar"
    assert not fs.path.exists()


def test_quarantine_raises_error():
    """
    arrange: Nothing.
    act: Call quarantine.
    assert: A QuarantineSharedFilesystemError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(errors.QuarantineSharedFilesystemError):
        shared_fs.move_to_quarantine(runner_name)
