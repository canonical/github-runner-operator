# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions to operate on the storage holding the metrics of the runners."""
import logging
import shutil
from pathlib import Path
from typing import Iterator

from errors import (
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
)
from metrics_common.storage import MetricsStorage, FILESYSTEM_QUARANTINE_PATH

DIR_NO_MOUNTPOINT_EXIT_CODE = 32

logger = logging.getLogger(__name__)

FILESYSTEM_OWNER = "ubuntu:ubuntu"
FILESYSTEM_BASE_PATH = Path("/home/ubuntu/runner-fs")
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
        raise CreateMetricsStorageError(
            "Failed to create metrics storage directories"
        ) from exc

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
            logger.error("Failed to get shared filesystem for runner %s", directory.name)
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
        raise GetMetricsStorageError(f"Shared filesystem for runner {runner_name} not found.")

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
        raise DeleteMetricsStorageError("Failed to remove metrics storage") from exc
