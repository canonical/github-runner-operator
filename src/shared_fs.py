#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions to operate on the shared filesystem between the charm and the runners."""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from errors import CreateSharedFilesystemError, SharedFilesystemNotFoundError, SubprocessError
from utilities import execute_command

FILESYSTEM_BASE_PATH = Path("/home/ubuntu/runner-fs")
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


def create(runner_name: str) -> SharedFilesystem:
    """Create a shared filesystem for the runner.

    Args:
        runner_name: The name of the runner.

    Returns:
        The shared filesystem object.

    Raises:
        CreateSharedFilesystemError: If the command fails.
    """
    FILESYSTEM_BASE_PATH.mkdir(exist_ok=True)
    runner_fs_path = FILESYSTEM_BASE_PATH / runner_name
    runner_fs_path.mkdir()
    runner_image_path = FILESYSTEM_BASE_PATH / f"{runner_name}.img"

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
        execute_command(["sudo", "chown", "ubuntu:ubuntu", str(runner_fs_path)], check_exit=True)
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


def delete(runner_name: str) -> None:
    """Delete the shared filesystem for the runner.

    Args:
        runner_name: The name of the runner.

    Raises:
        NotFoundError: If the shared filesystem is not found.
    """
    runner_fs = get(runner_name)
    runner_image_path = FILESYSTEM_BASE_PATH / f"{runner_name}.img"

    execute_command(
        ["sudo", "umount", str(runner_fs.path)],
        check_exit=True,
    )
    runner_image_path.unlink(missing_ok=True)
    shutil.rmtree(runner_fs.path)


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
