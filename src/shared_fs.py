#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions to operate on the shared filesystem between the charm and the runners."""
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from errors import (
    CreateSharedFilesystemError,
    DeleteSharedFilesystemError,
    QuarantineSharedFilesystemError,
    SharedFilesystemNotFoundError,
    SubprocessError,
)
from utilities import execute_command

FILESYSTEM_OWNER = "ubuntu:ubuntu"
FILESYSTEM_BASE_PATH = Path("/home/ubuntu/runner-fs")
FILESYSTEM_IMAGES_PATH = Path("/home/ubuntu/runner-fs-images")
FILESYSTEM_QUARANTINE_PATH = Path("/home/ubuntu/runner-fs-quarantine")
FILESYSTEM_SIZE = "1M"


@dataclass
class SharedFilesystem:
    """Shared filesystem between the charm and the runners.

    Attributes:
        path: The path of the shared filesystem inside the charm.
        runner_name: The name of the associated runner.
    Returns:
        The shared filesystem.
    """

    path: Path
    runner_name: str


def _get_runner_image_path(runner_name: str) -> Path:
    """Get the path of the runner image.

    Args:
        runner_name: The name of the runner.

    Returns:
        The path of the runner image.
    """
    return FILESYSTEM_IMAGES_PATH / f"{runner_name}.img"


def create(runner_name: str) -> SharedFilesystem:
    """Create a shared filesystem for the runner.

    The method is not idempotent and will raise an exception
    if the shared filesystem already exists.

    Args:
        runner_name: The name of the runner.

    Returns:
        The shared filesystem object.

    Raises:
        CreateSharedFilesystemError: If the creation of the shared filesystem fails.
    """
    try:
        FILESYSTEM_BASE_PATH.mkdir(exist_ok=True)
        FILESYSTEM_IMAGES_PATH.mkdir(exist_ok=True)
        FILESYSTEM_QUARANTINE_PATH.mkdir(exist_ok=True)
    except OSError as exc:
        raise CreateSharedFilesystemError(
            "Failed to create shared filesystem base path or images path"
        ) from exc

    runner_fs_path = FILESYSTEM_BASE_PATH / runner_name

    try:
        runner_fs_path.mkdir()
    except FileExistsError as exc:
        raise CreateSharedFilesystemError(
            f"Shared filesystem for runner {runner_name} already exists."
        ) from exc

    runner_image_path = _get_runner_image_path(runner_name)

    try:
        execute_command(
            ["dd", "if=/dev/zero", f"of={runner_image_path}", f"bs={FILESYSTEM_SIZE}", "count=1"],
            check_exit=True,
        )
        execute_command(["mkfs.ext4", f"{runner_image_path}"], check_exit=True)
        execute_command(
            ["sudo", "mount", "-o", "loop", str(runner_image_path), str(runner_fs_path)],
            check_exit=True,
        )
        execute_command(["sudo", "chown", FILESYSTEM_OWNER, str(runner_fs_path)], check_exit=True)
    except SubprocessError as exc:
        raise CreateSharedFilesystemError(
            f"Failed to create shared filesystem for runner {runner_name}"
        ) from exc
    return SharedFilesystem(runner_fs_path, runner_name)


def list_all() -> Iterator[SharedFilesystem]:
    """List the shared filesystems.

    Returns:
        An iterator over shared filesystems.
    """
    if not FILESYSTEM_BASE_PATH.exists():
        return

    directories = (entry for entry in FILESYSTEM_BASE_PATH.iterdir() if entry.is_dir())
    for directory in directories:
        yield SharedFilesystem(path=directory, runner_name=directory.name)


def get(runner_name: str) -> SharedFilesystem:
    """Get the shared filesystem for the runner.

    Args:
        runner_name: The name of the runner.

    Returns:
        The shared filesystem object.

    Raises:
        SharedFilesystemNotFoundError: If the shared filesystem is not found.
    """
    if not (runner_fs := FILESYSTEM_BASE_PATH.joinpath(runner_name)).exists():
        raise SharedFilesystemNotFoundError(
            f"Shared filesystem for runner {runner_name} not found."
        )
    return SharedFilesystem(runner_fs, runner_name)


def delete(runner_name: str) -> None:
    """Delete the shared filesystem for the runner.

    Args:
        runner_name: The name of the runner.

    Raises:
        DeleteSharedFilesystemError: If the shared filesystem could not be deleted.
    """
    try:
        runner_fs = get(runner_name)
    except SharedFilesystemNotFoundError as exc:
        raise DeleteSharedFilesystemError() from exc
    runner_image_path = _get_runner_image_path(runner_name)

    try:
        execute_command(
            ["sudo", "umount", str(runner_fs.path)],
            check_exit=True,
        )
    except SubprocessError as exc:
        raise DeleteSharedFilesystemError(
            f"Failed to unmount shared filesystem for runner {runner_name}"
        ) from exc
    try:
        runner_image_path.unlink(missing_ok=True)
    except OSError as exc:
        raise DeleteSharedFilesystemError(
            "Failed to remove runner image for shared filesystem"
        ) from exc

    try:
        shutil.rmtree(runner_fs.path)
    except OSError as exc:
        raise DeleteSharedFilesystemError("Failed to remove shared filesystem") from exc


def move_to_quarantine(runner_name: str) -> None:
    """Archive the shared filesystem for the runner and delete it.

    Args:
        runner_name: The name of the runner.

    Raises:
        QuarantineSharedFilesystemError: If the shared filesystem could not be quarantined.
        DeleteSharedFilesystemError: If the shared filesystem could not be deleted.
    """
    try:
        runner_fs = get(runner_name)
    except SharedFilesystemNotFoundError as exc:
        raise QuarantineSharedFilesystemError() from exc

    tarfile_path = FILESYSTEM_QUARANTINE_PATH.joinpath(runner_name).with_suffix(".tar.gz")
    try:
        with tarfile.open(tarfile_path, "w:gz") as tar:
            tar.add(runner_fs.path, arcname=runner_fs.path.name)
    except OSError as exc:
        raise QuarantineSharedFilesystemError(
            f"Failed to archive shared filesystem for runner {runner_name}"
        ) from exc

    delete(runner_name)
