#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions to operate on the shared fileystem between the charm and the runners."""
from dataclasses import dataclass
from pathlib import Path

from utilities import execute_command


FILESYSTEM_PATH = Path("/home/ubuntu/runner-fs")
FILESYSTEM_SIZE = "1M"


@dataclass
class SharedFilesystem:
    """Shared filesystem between the charm and the runners.

    Attrs:
        path: The path of the shared filesystem inside the charm.
        runner_name: The name of the associated runner.
    """
    path: Path
    runner_name: str


def create(runner_name: str) -> None:
    """Create a shared filesystem for the runner.

        Args:
            runner_name: The name of the runner.
    """
    FILESYSTEM_PATH.mkdir(exist_ok=True)
    runner_fs_path = FILESYSTEM_PATH / runner_name
    runner_fs_path.mkdir()
    runner_image_path = FILESYSTEM_PATH / f"{runner_name}.img"

    execute_command(
        ["dd", "if=/dev/zero", f"of={runner_image_path}", f"bs={FILESYSTEM_SIZE}",
         "count=1"], check_exit=True)
    execute_command(["mkfs.ext4", f"{runner_image_path}"], check_exit=True)
    execute_command(["sudo", "mount", "-o", "loop", runner_image_path,
                     runner_fs_path], check_exit=True)
    execute_command(["sudo", "chown", "ubuntu:ubuntu", runner_fs_path], check_exit=True)


def list() -> list[SharedFilesystem]:
    """List the shared filesystems."""
    pass

def delete(runner_name: str) -> None:
    """Delete the shared filesystem for the runner.

        Args:
            runner_name: The name of the runner.
    """
    pass


def get(runner_name: str) -> SharedFilesystem:
    """Get the shared filesystem for the runner.

        Args:
            runner_name: The name of the runner.
    """
    return SharedFilesystem(FILESYSTEM_PATH / runner_name, runner_name)
