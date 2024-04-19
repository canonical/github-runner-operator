# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions to operate on the shared filesystem between the charm and the runners."""
import logging
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from errors import (
    CreateMetricsStorageError,
    CreateSharedFilesystemError,
    DeleteSharedFilesystemError,
    GetSharedFilesystemError,
    QuarantineSharedFilesystemError,
    SharedFilesystemMountError,
    SubprocessError,
)
from metrics_common.storage import MetricsStorage
from utilities import execute_command

DIR_NO_MOUNTPOINT_EXIT_CODE = 32

logger = logging.getLogger(__name__)

FILESYSTEM_OWNER = "ubuntu:ubuntu"
FILESYSTEM_BASE_PATH = Path("/home/ubuntu/runner-fs")
FILESYSTEM_QUARANTINE_PATH = Path("/home/ubuntu/runner-fs-quarantine")
FILESYSTEM_SIZE = "1M"


def _get_runner_fs_path(runner_name: str) -> Path:
    """Get the path of the runner shared filesystem.

    Args:
        runner_name: The name of the runner.

    Returns:
        The path of the runner shared filesystem.
    """
    return FILESYSTEM_BASE_PATH / runner_name


def create(runner_name: str) -> MetricsStorage:
    """Create a shared filesystem for the runner.

    The method is not idempotent and will raise an exception
    if the shared filesystem already exists.

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
        raise CreateMetricsStorageError(
            "Failed to create shared filesystem base path or images path"
        ) from exc

    runner_fs_path = _get_runner_fs_path(runner_name)

    try:
        runner_fs_path.mkdir()
    except FileExistsError as exc:
        raise CreateSharedFilesystemError(
            f"Shared filesystem for runner {runner_name} already exists."
        ) from exc

    return MetricsStorage(runner_fs_path, runner_name)


#
# def list_all() -> Generator[SharedFilesystem, None, None]:
#     """List the shared filesystems.
#
#     Yields:
#         A shared filesystem instance.
#     """
#     if not FILESYSTEM_BASE_PATH.exists():
#         return
#
#     directories = (entry for entry in FILESYSTEM_BASE_PATH.iterdir() if entry.is_dir())
#     for directory in directories:
#         try:
#             fs = get(runner_name=directory.name)
#         except GetSharedFilesystemError:
#             logger.error("Failed to get shared filesystem for runner %s", directory.name)
#         else:
#             yield fs
#
#
# def get(runner_name: str) -> SharedFilesystem:
#     """Get the shared filesystem for the runner.
#
#     Mounts the filesystem if it is not currently mounted.
#
#     Args:
#         runner_name: The name of the runner.
#
#     Returns:
#         The shared filesystem object.
#
#     Raises:
#         GetSharedFilesystemError: If the shared filesystem could not be retrieved/mounted.
#     """
#     runner_fs_path = _get_runner_fs_path(runner_name)
#     if not runner_fs_path.exists():
#         raise GetSharedFilesystemError(f"Shared filesystem for runner {runner_name} not found.")
#
#     return SharedFilesystem(runner_fs_path, runner_name)
#
#
# def delete(runner_name: str) -> None:
#     """Delete the shared filesystem for the runner.
#
#     Args:
#         runner_name: The name of the runner.
#
#     Raises:
#         DeleteSharedFilesystemError: If the shared filesystem could not be deleted.
#     """
#     runner_fs_path = _get_runner_fs_path(runner_name=runner_name)
#
#     try:
#         shutil.rmtree(runner_fs_path)
#     except OSError as exc:
#         raise DeleteSharedFilesystemError("Failed to remove shared filesystem") from exc
#
#
# def move_to_quarantine(runner_name: str) -> None:
#     """Archive the shared filesystem for the runner and delete it.
#
#     Args:
#         runner_name: The name of the runner.
#
#     Raises:
#         QuarantineSharedFilesystemError: If the shared filesystem could not be quarantined.
#         DeleteSharedFilesystemError: If the shared filesystem could not be deleted.
#     """
#     try:
#         runner_fs = get(runner_name)
#     except GetSharedFilesystemError as exc:
#         raise QuarantineSharedFilesystemError(
#             f"Failed to get shared filesystem for runner {runner_name}"
#         ) from exc
#
#     tarfile_path = FILESYSTEM_QUARANTINE_PATH.joinpath(runner_name).with_suffix(".tar.gz")
#     try:
#         with tarfile.open(tarfile_path, "w:gz") as tar:
#             tar.add(runner_fs.path, arcname=runner_fs.path.name)
#     except OSError as exc:
#         raise QuarantineSharedFilesystemError(
#             f"Failed to archive shared filesystem for runner {runner_name}"
#         ) from exc
#
#     try:
#         delete(runner_name)
#     # 2024/04/02 - We should define a new error, wrap it and re-raise it.
#     except DeleteSharedFilesystemError:  # pylint: disable=try-except-raise
#         raise
