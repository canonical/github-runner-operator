#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions defining the metrics storage."""
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol

from errors import GetMetricsStorageError, QuarantineMetricsStorageError, DeleteMetricsStorageError

FILESYSTEM_QUARANTINE_PATH = Path("/home/ubuntu/runner-fs-quarantine")


@dataclass
class MetricsStorage:
    """Storage for the metrics.

    Attributes:
        path: The path to the directory holding the metrics inside the charm.
        runner_name: The name of the associated runner.
    """

    path: Path
    runner_name: str


class StorageManager(Protocol):
    """A protocol defining the methods for managing the metrics storage.

    Attributes:
        create: Method to create a new storage. Returns the created storage.
          Raises an exception CreateMetricsStorageError if the storage already exists.
        list_all: Method to list all storages.
        get: Method to get a storage by name.
        delete: Method to delete a storage by name.
        move_to_quarantine: Method to move a storage to quarantine.
    """

    create: Callable[[str], MetricsStorage]
    list_all: Callable[[], Iterator[MetricsStorage]]
    get: Callable[[str], MetricsStorage]
    delete: Callable[[str], None]
    move_to_quarantine: Callable[[str], None]


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
