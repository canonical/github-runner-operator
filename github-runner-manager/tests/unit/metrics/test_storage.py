#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import os
import tarfile
from grp import getgrgid
from pathlib import Path
from pwd import getpwuid

import pytest

from github_runner_manager.errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
    QuarantineMetricsStorageError,
)
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.metrics import storage
from github_runner_manager.metrics.storage import (
    _FILESYSTEM_BASE_DIR_NAME,
    _FILESYSTEM_QUARANTINE_DIR_NAME,
    MetricsStorage,
    StorageManager,
)


# We assume the process running the tests is running as a user
# that can write to the temporary directory.
@pytest.fixture(autouse=True, scope="function")
def fix_user_group(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "github_runner_manager.constants.RUNNER_MANAGER_USER",
        (passwd := getpwuid(os.getuid())).pw_name,
    )
    monkeypatch.setattr(
        "github_runner_manager.constants.RUNNER_MANAGER_GROUP",
        getgrgid(passwd.pw_gid).gr_name,
    )


@pytest.fixture(autouse=True, name="filesystem_paths")
def filesystem_paths_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Mock the hardcoded filesystem paths."""
    monkeypatch.setattr(storage.Path, "expanduser", lambda *args: tmp_path)
    return {
        "base": tmp_path / _FILESYSTEM_BASE_DIR_NAME,
        "quarantine": tmp_path / _FILESYSTEM_QUARANTINE_DIR_NAME,
    }


def test_create_creates_directory():
    """
    arrange: Given a runner name and a path for the storage.
    act: Call create.
    assert: The directory is created.
    """
    runner_name = InstanceID.build("prefix")

    fs = StorageManager("prefix").create(runner_name)

    assert fs.path.exists()
    assert fs.path.is_dir()


def test_create_raises_exception_if_already_exists():
    """
    arrange: Given a runner name and an already existing shared filesystem.
    act: Call create.
    assert: The expected exception is raised.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")
    storage_manager.create(runner_name)

    with pytest.raises(CreateMetricsStorageError):
        storage_manager.create(runner_name)


def test_list_all():
    """
    arrange: Create metric storages for multiple runners.
    act: Call list_all.
    assert: A generator listing all the shared filesystems is returned.
    """
    runner_names = [InstanceID.build("prefix") for _ in range(3)]
    storage_manager = StorageManager("prefix")
    for runner_name in runner_names:
        storage_manager.create(runner_name)

    fs_list = list(storage_manager.list_all())

    assert len(fs_list) == 3
    for fs in fs_list:
        assert isinstance(fs, storage.MetricsStorage)
        assert fs.instance_id in runner_names


def test_list_all_empty():
    """
    arrange: Nothing.
    act: Call list_all.
    assert: An empty iterator is returned.
    """
    fs_list = list(StorageManager("prefix").list_all())

    assert len(fs_list) == 0


def test_delete():
    """
    arrange: Create metrics storage for a runner.
    act: Call delete
    assert: The storage is deleted.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")
    storage_manager.create(runner_name)

    storage_manager.delete(runner_name)

    with pytest.raises(GetMetricsStorageError):
        storage_manager.get(runner_name)


def test_delete_raises_error():
    """
    arrange: Nothing.
    act: Call delete.
    assert: A DeleteMetricsStorageError is raised.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")

    with pytest.raises(DeleteMetricsStorageError):
        storage_manager.delete(runner_name)


def test_get():
    """
    arrange: Given a runner name.
    act: Call create and get.
    assert: A metrics storage object for this runner is returned.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")

    storage_manager.create(runner_name)
    ms = storage_manager.get(runner_name)

    assert isinstance(ms, MetricsStorage)
    assert ms.instance_id == runner_name


def test_get_raises_error_if_not_found():
    """
    arrange: Nothing.
    act: Call get.
    assert: A GetMetricsStorageError is raised.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")

    with pytest.raises(GetMetricsStorageError):
        storage_manager.get(runner_name)


def test_quarantine(filesystem_paths: dict[str, Path], tmp_path: Path):
    """
    arrange: Create a storage for a runner with a file in it.
    act: Call quarantine.
    assert: The storage is moved to the quarantine.
    """
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")
    ms = storage_manager.create(runner_name)
    ms.path.joinpath("test.txt").write_text("foo bar")

    storage_manager.move_to_quarantine(runner_name)

    tarfile_path = filesystem_paths["quarantine"].joinpath(str(runner_name)).with_suffix(".tar.gz")
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
    runner_name = InstanceID.build("prefix")
    storage_manager = StorageManager("prefix")

    with pytest.raises(QuarantineMetricsStorageError):
        storage_manager.move_to_quarantine(runner_name)
