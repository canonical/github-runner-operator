#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
import tarfile
from pathlib import Path

import pytest
from github_runner_manager.metrics import MetricsStorage, storage

from errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
    QuarantineMetricsStorageError,
)


@pytest.fixture(autouse=True, name="filesystem_paths")
def filesystem_paths_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Mock the hardcoded filesystem paths."""
    ms_path = tmp_path / "runner-fs"
    ms_quarantine_path = tmp_path / "quarantine"
    monkeypatch.setattr(storage, "FILESYSTEM_BASE_PATH", ms_path)
    monkeypatch.setattr(storage, "FILESYSTEM_QUARANTINE_PATH", ms_quarantine_path)
    return {"base": ms_path, "quarantine": ms_quarantine_path}


def test_create_creates_directory():
    """
    arrange: Given a runner name and a path for the storage.
    act: Call create.
    assert: The directory is created.
    """
    runner_name = secrets.token_hex(16)

    fs = storage.create(runner_name)

    assert fs.path.exists()
    assert fs.path.is_dir()


def test_create_raises_exception_if_already_exists():
    """
    arrange: Given a runner name and an already existing shared filesystem.
    act: Call create.
    assert: The expected exception is raised.
    """
    runner_name = secrets.token_hex(16)
    storage.create(runner_name)

    with pytest.raises(CreateMetricsStorageError):
        storage.create(runner_name)


def test_list_all():
    """
    arrange: Create metric storages for multiple runners.
    act: Call list_all.
    assert: A generator listing all the shared filesystems is returned.
    """
    runner_names = [secrets.token_hex(16) for _ in range(3)]
    for runner_name in runner_names:
        storage.create(runner_name)

    fs_list = list(storage.list_all())

    assert len(fs_list) == 3
    for fs in fs_list:
        assert isinstance(fs, storage.MetricsStorage)
        assert fs.runner_name in runner_names


def test_list_all_empty():
    """
    arrange: Nothing.
    act: Call list_all.
    assert: An empty iterator is returned.
    """
    fs_list = list(storage.list_all())

    assert len(fs_list) == 0


def test_delete():
    """
    arrange: Create metrics storage for a runner.
    act: Call delete
    assert: The storage is deleted.
    """
    runner_name = secrets.token_hex(16)
    storage.create(runner_name)

    storage.delete(runner_name)

    with pytest.raises(GetMetricsStorageError):
        storage.get(runner_name)


def test_delete_raises_error():
    """
    arrange: Nothing.
    act: Call delete.
    assert: A DeleteMetricsStorageError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(DeleteMetricsStorageError):
        storage.delete(runner_name)


def test_get():
    """
    arrange: Given a runner name.
    act: Call create and get.
    assert: A metrics storage object for this runner is returned.
    """
    runner_name = secrets.token_hex(16)

    storage.create(runner_name)
    ms = storage.get(runner_name)

    assert isinstance(ms, MetricsStorage)
    assert ms.runner_name == runner_name


def test_get_raises_error_if_not_found():
    """
    arrange: Nothing.
    act: Call get.
    assert: A GetMetricsStorageError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(GetMetricsStorageError):
        storage.get(runner_name)


def test_quarantine(filesystem_paths: dict[str, Path], tmp_path: Path):
    """
    arrange: Create a storage for a runner with a file in it.
    act: Call quarantine.
    assert: The storage is moved to the quarantine.
    """
    runner_name = secrets.token_hex(16)
    ms = storage.create(runner_name)
    ms.path.joinpath("test.txt").write_text("foo bar")

    storage.move_to_quarantine(storage, runner_name)

    tarfile_path = filesystem_paths["quarantine"].joinpath(runner_name).with_suffix(".tar.gz")
    assert tarfile_path.exists()
    tarfile.open(tarfile_path).extractall(path=tmp_path)
    assert tmp_path.joinpath(f"{runner_name}/test.txt").exists()
    assert tmp_path.joinpath(f"{runner_name}/test.txt").read_text(encoding="utf-8") == "foo bar"
    assert not ms.path.exists()


def test_quarantine_raises_error():
    """
    arrange: Nothing.
    act: Call quarantine.
    assert: A QuarantineMetricsStorageError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(QuarantineMetricsStorageError):
        storage.move_to_quarantine(storage, runner_name)
