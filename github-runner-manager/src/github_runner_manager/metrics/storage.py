#  Copyright 2025 Canonical Ltd.
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

from github_runner_manager import constants
from github_runner_manager.errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
    QuarantineMetricsStorageError,
)
from github_runner_manager.manager.models import InstanceID

_FILESYSTEM_BASE_DIR_NAME = "runner-fs"
_FILESYSTEM_QUARANTINE_DIR_NAME = "runner-fs-quarantine"

logger = logging.getLogger(__name__)


@dataclass
class MetricsStorage:
    """Storage for the metrics.

    Attributes:
        path: The path to the directory holding the metrics inside the charm.
        instance_id: The name of the associated runner.
    """

    path: Path
    instance_id: InstanceID


class StorageManagerProtocol(Protocol):  # pylint: disable=too-few-public-methods
    """A protocol defining the methods for managing the metrics storage.

    Attributes:
        create: Method to create a new storage. Returns the created storage.
          Raises an exception CreateMetricsStorageError if the storage already exists.
        list_all: Method to list all storages.
        get: Method to get a storage by name.
        delete: Method to delete a storage by name.
        move_to_quarantine: Method to archive and delete a storage by name.
    """

    create: Callable[[str], MetricsStorage]
    list_all: Callable[[], Iterator[MetricsStorage]]
    get: Callable[[str], MetricsStorage]
    delete: Callable[[str], None]
    move_to_quarantine: Callable[[str], None]


class StorageManager(StorageManagerProtocol):
    """Manager for the metrics storage."""

    def __init__(self, prefix: str) -> None:
        """Initialize the storage manager.

        Args:
            prefix: Prefix for the application (charm application unit name).
        """
        self._base_dir = (
            Path(f"~{constants.RUNNER_MANAGER_USER}").expanduser() / _FILESYSTEM_BASE_DIR_NAME
        )
        self._quarantine_dir = (
            Path(f"~{constants.RUNNER_MANAGER_USER}").expanduser()
            / _FILESYSTEM_QUARANTINE_DIR_NAME
        )
        self._prefix = prefix

    def create(self, instance_id: InstanceID) -> MetricsStorage:
        """Create metrics storage for the runner.

        The method is not idempotent and will raise an exception
        if the storage already exists.

        Args:
            instance_id: The name of the runner.

        Returns:
            The metrics storage object.

        Raises:
            CreateMetricsStorageError: If the creation of the shared filesystem fails.
        """
        try:
            self._base_dir.mkdir(exist_ok=True)
            # this could be executed as root (e.g. during a charm hook), therefore set permissions
            shutil.chown(
                self._base_dir,
                user=constants.RUNNER_MANAGER_USER,
                group=constants.RUNNER_MANAGER_GROUP,
            )
            logger.debug(
                "Changed ownership of %s to %s:%s",
                _FILESYSTEM_BASE_DIR_NAME,
                constants.RUNNER_MANAGER_USER,
                constants.RUNNER_MANAGER_GROUP,
            )

            self._quarantine_dir.mkdir(exist_ok=True)
            shutil.chown(
                self._quarantine_dir,
                user=constants.RUNNER_MANAGER_USER,
                group=constants.RUNNER_MANAGER_GROUP,
            )
            logger.debug(
                "Changed ownership of %s to %s:%s",
                self._quarantine_dir,
                constants.RUNNER_MANAGER_USER,
                constants.RUNNER_MANAGER_GROUP,
            )

        except OSError as exc:
            raise CreateMetricsStorageError(
                "Failed to create metrics storage directories"
            ) from exc

        runner_fs_path = self._get_runner_fs_path(instance_id=instance_id)

        try:
            runner_fs_path.mkdir()
        except FileExistsError as exc:
            raise CreateMetricsStorageError(
                f"Metrics storage for runner {instance_id} already exists."
            ) from exc

        return MetricsStorage(runner_fs_path, instance_id)

    def list_all(self) -> Iterator[MetricsStorage]:
        """List all the metric storages.

        Yields:
            A metrics storage object.
        """
        if not self._base_dir.exists():
            return

        directories = (entry for entry in self._base_dir.iterdir() if entry.is_dir())
        for directory in directories:
            try:
                fs = self.get(instance_id=InstanceID.build_from_name(self._prefix, directory.name))
            except GetMetricsStorageError:
                logger.error("Failed to get metrics storage for runner %s", directory.name)
            except ValueError:
                logger.exception(
                    "Failed to get metrics storage for runner %s and prefix %s",
                    directory.name,
                    self._prefix,
                )
            else:
                yield fs

    def get(self, instance_id: InstanceID) -> MetricsStorage:
        """Get the metrics storage for the runner.

        Args:
            instance_id: The name of the runner.

        Returns:
            The metrics storage object.

        Raises:
            GetMetricsStorageError: If the storage does not exist.
        """
        runner_fs_path = self._get_runner_fs_path(
            instance_id=instance_id,
        )
        if not runner_fs_path.exists():
            raise GetMetricsStorageError(f"Metrics storage for runner {instance_id} not found.")

        return MetricsStorage(runner_fs_path, instance_id)

    def delete(self, instance_id: InstanceID) -> None:
        """Delete the metrics storage for the runner.

        Args:
            instance_id: The name of the runner.

        Raises:
            DeleteMetricsStorageError: If the storage could not be deleted.
        """
        runner_fs_path = self._get_runner_fs_path(instance_id=instance_id)

        try:
            shutil.rmtree(runner_fs_path)
        except OSError as exc:
            raise DeleteMetricsStorageError(
                f"Failed to remove metrics storage for runner {instance_id}"
            ) from exc

    def move_to_quarantine(
        self,
        instance_id: InstanceID,
    ) -> None:
        """Archive the metrics storage for the runner and delete it.

        Args:
            instance_id: The name of the runner.

        Raises:
            QuarantineMetricsStorageError: If the metrics storage could not be quarantined.
        """
        try:
            runner_fs = self.get(instance_id)
        except GetMetricsStorageError as exc:
            raise QuarantineMetricsStorageError(
                f"Failed to get metrics storage for runner {instance_id}"
            ) from exc

        tarfile_path = self._quarantine_dir.joinpath(str(instance_id)).with_suffix(".tar.gz")
        try:
            with tarfile.open(tarfile_path, "w:gz") as tar:
                tar.add(runner_fs.path, arcname=runner_fs.path.name)
        except OSError as exc:
            raise QuarantineMetricsStorageError(
                f"Failed to archive metrics storage for runner {instance_id}"
            ) from exc

        try:
            self.delete(instance_id)
        except DeleteMetricsStorageError as exc:
            raise QuarantineMetricsStorageError(
                f"Failed to delete metrics storage for runner {instance_id}"
            ) from exc

    def _get_runner_fs_path(self, instance_id: InstanceID) -> Path:
        """Get the path of the runner metrics storage.

        Args:
            instance_id: The name of the runner.

        Returns:
            The path of the runner shared filesystem.
        """
        return self._base_dir / str(instance_id)
