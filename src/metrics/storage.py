#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions defining the metrics storage.

It contains a protocol and reference implementation.
"""
import logging
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol

from errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
    QuarantineMetricsStorageError,
)

FILESYSTEM_OWNER = "ubuntu:ubuntu"
FILESYSTEM_BASE_PATH = Path("/home/ubuntu/runner-fs")
FILESYSTEM_QUARANTINE_PATH = Path("/home/ubuntu/runner-fs-quarantine")

logger = logging.getLogger(__name__)


@dataclass
class MetricsStorage:
    """Storage for the metrics.

    Attributes:
        path: The path to the directory holding the metrics inside the charm.
        runner_name: The name of the associated runner.
    """

    path: Path
    runner_name: str


class StorageManager(Protocol):  # pylint: disable=too-few-public-methods
    """A protocol defining the methods for managing the metrics storage.

    Attributes:
        create: Method to create a new storage. Returns the created storage.
          Raises an exception CreateMetricsStorageError if the storage already exists.
        list_all: Method to list all storages.
        get: Method to get a storage by name.
        delete: Method to delete a storage by name.
    """

    create: Callable[[str], MetricsStorage]
    list_all: Callable[[], Iterator[MetricsStorage]]
    get: Callable[[str], MetricsStorage]
    delete: Callable[[str], None]


def _get_runner_fs_path(runner_name: str) -> Path:
    """Get the path of the runner shared filesystem.

    Args:
        runner_name: The name of the runner.

    Returns:
        The path of the runner shared filesystem.
    """
    return FILESYSTEM_BASE_PATH / runner_name


def create(runner_name: str) -> MetricsStorage:
    """Create metrics storage for the runner.

    The method is not idempotent and will raise an exception
    if the storage already exists.

    Args:
        runner_name: The name of the runner.

    Returns:
        The metrics storage object.

    Raises:
        CreateMetricsStorageError: If the creation of the shared filesystem fails.
    """
    try:
        FILESYSTEM_BASE_PATH.mkdir(exist_ok=True)
        FILESYSTEM_QUARANTINE_PATH.mkdir(exist_ok=True)
    except OSError as exc:
        raise CreateMetricsStorageError("Failed to create metrics storage directories") from exc

    runner_fs_path = _get_runner_fs_path(runner_name)

    try:
        runner_fs_path.mkdir()
    except FileExistsError as exc:
        raise CreateMetricsStorageError(
            f"Metrics storage for runner {runner_name} already exists."
        ) from exc

    return MetricsStorage(runner_fs_path, runner_name)


def list_all() -> Iterator[MetricsStorage]:
    """List all the metric storages.

    Yields:
        A metrics storage object.
    """
    if not FILESYSTEM_BASE_PATH.exists():
        return

    directories = (entry for entry in FILESYSTEM_BASE_PATH.iterdir() if entry.is_dir())
    for directory in directories:
        try:
            fs = get(runner_name=directory.name)
        except GetMetricsStorageError:
            logger.error("Failed to get metrics storage for runner %s", directory.name)
        else:
            yield fs


def get(runner_name: str) -> MetricsStorage:
    """Get the metrics storage for the runner.

    Args:
        runner_name: The name of the runner.

    Returns:
        The metrics storage object.

    Raises:
        GetMetricsStorageError: If the storage does not exist.
    """
    runner_fs_path = _get_runner_fs_path(runner_name)
    if not runner_fs_path.exists():
        raise GetMetricsStorageError(f"Metrics storage for runner {runner_name} not found.")

    return MetricsStorage(runner_fs_path, runner_name)


def delete(runner_name: str) -> None:
    """Delete the metrics storage for the runner.

    Args:
        runner_name: The name of the runner.

    Raises:
        DeleteMetricsStorageError: If the storage could not be deleted.
    """
    runner_fs_path = _get_runner_fs_path(runner_name=runner_name)

    try:
        shutil.rmtree(runner_fs_path)
    except OSError as exc:
        raise DeleteMetricsStorageError(
            f"Failed to remove metrics storage for runner {runner_name}"
        ) from exc


def move_to_quarantine(storage_manager: StorageManager, runner_name: str) -> None:
    """Archive the metrics storage for the runner and delete it.

    Args:
        storage_manager: The storage manager.
        runner_name: The name of the runner.

    Raises:
        QuarantineMetricsStorageError: If the metrics storage could not be quarantined.
    """
    try:
        runner_fs = storage_manager.get(runner_name)
    except GetMetricsStorageError as exc:
        raise QuarantineMetricsStorageError(
            f"Failed to get metrics storage for runner {runner_name}"
        ) from exc

    tarfile_path = FILESYSTEM_QUARANTINE_PATH.joinpath(runner_name).with_suffix(".tar.gz")
    try:
        with tarfile.open(tarfile_path, "w:gz") as tar:
            tar.add(runner_fs.path, arcname=runner_fs.path.name)
    except OSError as exc:
        raise QuarantineMetricsStorageError(
            f"Failed to archive metrics storage for runner {runner_name}"
        ) from exc

    try:
        storage_manager.delete(runner_name)
    except DeleteMetricsStorageError as exc:
        raise QuarantineMetricsStorageError(
            f"Failed to delete metrics storage for runner {runner_name}"
        ) from exc
