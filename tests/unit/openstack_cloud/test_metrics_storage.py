# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

import openstack_cloud.metrics_storage as metrics_storage
from errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
)
from metrics_common.storage import MetricsStorage

MOUNTPOINT_FAILURE_EXIT_CODE = 1


@pytest.fixture(autouse=True, name="filesystem_paths")
def filesystem_paths_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Mock the hardcoded filesystem paths."""
    ms_path = tmp_path / "runner-fs"
    ms_quarantine_path = tmp_path / "quarantine"
    monkeypatch.setattr(metrics_storage, "FILESYSTEM_BASE_PATH", ms_path)
    monkeypatch.setattr(metrics_storage, "FILESYSTEM_QUARANTINE_PATH", ms_quarantine_path)
    return {"base": ms_path, "quarantine": ms_quarantine_path}


def test_create_creates_directory():
    """
    arrange: Given a runner name and a path for the storage.
    act: Call create.
    assert: The directory is created.
    """
    runner_name = secrets.token_hex(16)

    fs = metrics_storage.create(runner_name)

    assert fs.path.exists()
    assert fs.path.is_dir()


def test_create_raises_exception_if_already_exists():
    """
    arrange: Given a runner name and an already existing shared filesystem.
    act: Call create.
    assert: The expected exception is raised.
    """
    runner_name = secrets.token_hex(16)
    metrics_storage.create(runner_name)

    with pytest.raises(CreateMetricsStorageError):
        metrics_storage.create(runner_name)


def test_list_all():
    """
    arrange: Create metric storages for multiple runners.
    act: Call list_all.
    assert: A generator listing all the shared filesystems is returned.
    """
    runner_names = [secrets.token_hex(16) for _ in range(3)]
    for runner_name in runner_names:
        metrics_storage.create(runner_name)

    fs_list = list(metrics_storage.list_all())

    assert len(fs_list) == 3
    for fs in fs_list:
        assert isinstance(fs, metrics_storage.MetricsStorage)
        assert fs.runner_name in runner_names


def test_list_all_empty():
    """
    arrange: Nothing.
    act: Call list_all.
    assert: An empty iterator is returned.
    """
    fs_list = list(metrics_storage.list_all())

    assert len(fs_list) == 0


def test_delete():
    """
    arrange: Create metrics storage for a runner.
    act: Call delete
    assert: The storage is deleted.
    """
    runner_name = secrets.token_hex(16)
    metrics_storage.create(runner_name)

    metrics_storage.delete(runner_name)

    with pytest.raises(GetMetricsStorageError):
        metrics_storage.get(runner_name)


def test_delete_raises_error():
    """
    arrange: Nothing.
    act: Call delete.
    assert: A DeleteMetricsStorageError is raised.
    """
    runner_name = secrets.token_hex(16)

    with pytest.raises(DeleteMetricsStorageError):
        metrics_storage.delete(runner_name)


def test_get():
    """
    arrange: Given a runner name.
    act: Call create and get.
    assert: A metrics storage object for this runner is returned.
    """
    runner_name = secrets.token_hex(16)

    metrics_storage.create(runner_name)
    ms = metrics_storage.get(runner_name)

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
        metrics_storage.get(runner_name)
