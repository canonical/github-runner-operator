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
    CreateSharedFilesystemError,
    DeleteSharedFilesystemError,
    GetSharedFilesystemError,
    QuarantineSharedFilesystemError,
    SharedFilesystemMountError,
    SubprocessError,
)
from utilities import execute_command

DIR_NO_MOUNTPOINT_EXIT_CODE = 32

logger = logging.getLogger(__name__)

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


def _get_runner_fs_path(runner_name: str) -> Path:
    """Get the path of the runner shared filesystem.

    Args:
        runner_name: The name of the runner.

    Returns:
        The path of the runner shared filesystem.
    """
    return FILESYSTEM_BASE_PATH / runner_name


def _is_mountpoint(path: Path) -> bool:
    """Check if the path is a mountpoint.

    Args:
        path: The path to check.

    Returns:
        True if the path is a mountpoint, False otherwise.

    Raises:
        SharedFilesystemMountError: If the check fails.
    """
    _, ret_code = execute_command(["mountpoint", "-q", str(path)], check_exit=False)
    if ret_code not in (0, DIR_NO_MOUNTPOINT_EXIT_CODE):
        raise SharedFilesystemMountError(
            f"Failed to check if path {path} is a mountpoint. "
            f"mountpoint command return code: {ret_code}"
        )
    return ret_code == 0


def _mount(runner_fs_path: Path, runner_image_path: Path) -> None:
    """Mount the shared filesystem.

    Args:
        runner_fs_path: The path of the shared filesystem.
        runner_image_path: The path of the runner image.

    Raises:
        SharedFilesystemMountError: If the mount fails.
    """
    try:
        execute_command(
            ["sudo", "mount", "-o", "loop", str(runner_image_path), str(runner_fs_path)],
            check_exit=True,
        )
    except SubprocessError as exc:
        raise SharedFilesystemMountError(
            f"Failed to mount shared filesystem {runner_fs_path}"
        ) from exc


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

    runner_fs_path = _get_runner_fs_path(runner_name)

    try:
        runner_fs_path.mkdir()
    except FileExistsError as exc:
        raise CreateSharedFilesystemError(
            f"Shared filesystem for runner {runner_name} already exists."
        ) from exc

    runner_img_path = _get_runner_image_path(runner_name)

    try:
        execute_command(
            ["dd", "if=/dev/zero", f"of={runner_img_path}", f"bs={FILESYSTEM_SIZE}", "count=1"],
            check_exit=True,
        )
        execute_command(["mkfs.ext4", f"{runner_img_path}"], check_exit=True)
        _mount(runner_fs_path=runner_fs_path, runner_image_path=runner_img_path)
        execute_command(["sudo", "chown", FILESYSTEM_OWNER, str(runner_fs_path)], check_exit=True)
    except (SubprocessError, SharedFilesystemMountError) as exc:
        raise CreateSharedFilesystemError(
            f"Failed to create shared filesystem for runner {runner_name}"
        ) from exc
    return SharedFilesystem(runner_fs_path, runner_name)


def list_all() -> Generator[SharedFilesystem, None, None]:
    """List the shared filesystems.

    Yields:
        A shared filesystem instance.
    """
    if not FILESYSTEM_BASE_PATH.exists():
        return

    directories = (entry for entry in FILESYSTEM_BASE_PATH.iterdir() if entry.is_dir())
    for directory in directories:
        try:
            fs = get(runner_name=directory.name)
        except GetSharedFilesystemError:
            logger.error("Failed to get shared filesystem for runner %s", directory.name)
        else:
            yield fs


def get(runner_name: str) -> SharedFilesystem:
    """Get the shared filesystem for the runner.

    Mounts the filesystem if it is not currently mounted.

    Args:
        runner_name: The name of the runner.

    Returns:
        The shared filesystem object.

    Raises:
        GetSharedFilesystemError: If the shared filesystem could not be retrieved/mounted.
    """
    runner_fs_path = _get_runner_fs_path(runner_name)
    if not runner_fs_path.exists():
        raise GetSharedFilesystemError(f"Shared filesystem for runner {runner_name} not found.")

    try:
        is_mounted = _is_mountpoint(runner_fs_path)
    except SharedFilesystemMountError as exc:
        raise GetSharedFilesystemError(
            f"Failed to determine if shared filesystem is mounted for runner {runner_name}"
        ) from exc

    if not is_mounted:
        logger.info(
            "Shared filesystem for runner %s is not mounted (may happen after reboot). "
            "Will be mounted now.",
            runner_name,
        )
        runner_img_path = _get_runner_image_path(runner_name)
        try:
            _mount(runner_fs_path=runner_fs_path, runner_image_path=runner_img_path)
        except SharedFilesystemMountError as exc:
            raise GetSharedFilesystemError(
                f"Shared filesystem for runner {runner_name} could not be mounted."
            ) from exc

    return SharedFilesystem(runner_fs_path, runner_name)


def delete(runner_name: str) -> None:
    """Delete the shared filesystem for the runner.

    Args:
        runner_name: The name of the runner.

    Raises:
        DeleteSharedFilesystemError: If the shared filesystem could not be deleted.
    """
    runner_fs_path = _get_runner_fs_path(runner_name)
    if not runner_fs_path.exists():
        raise DeleteSharedFilesystemError(f"Shared filesystem for runner {runner_name} not found.")
    runner_image_path = _get_runner_image_path(runner_name)

    try:
        is_mounted = _is_mountpoint(runner_fs_path)
    except SharedFilesystemMountError as exc:
        raise DeleteSharedFilesystemError(
            f"Failed to determine if shared filesystem is mounted for runner {runner_name}"
        ) from exc

    if not is_mounted:
        logger.warning("Shared filesystem for runner %s is not mounted", runner_name)
    else:
        try:
            execute_command(
                ["sudo", "umount", str(runner_fs_path)],
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
        shutil.rmtree(runner_fs_path)
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
    except GetSharedFilesystemError as exc:
        raise QuarantineSharedFilesystemError(
            f"Failed to get shared filesystem for runner {runner_name}"
        ) from exc

    tarfile_path = FILESYSTEM_QUARANTINE_PATH.joinpath(runner_name).with_suffix(".tar.gz")
    try:
        with tarfile.open(tarfile_path, "w:gz") as tar:
            tar.add(runner_fs.path, arcname=runner_fs.path.name)
    except OSError as exc:
        raise QuarantineSharedFilesystemError(
            f"Failed to archive shared filesystem for runner {runner_name}"
        ) from exc

    try:
        delete(runner_name)
    except DeleteSharedFilesystemError:
        raise
