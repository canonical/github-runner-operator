# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities used by the charm."""

import logging
import os
import pathlib
import subprocess  # nosec B404
from typing import Any, Optional, Sequence, TypeVar

# we import the functions from the utilities module, these are used in the charm
from github_runner_manager.utilities import retry  # noqa: F401  pylint: disable=unused-import
from github_runner_manager.utilities import (  # noqa: F401  pylint: disable=unused-import
    secure_run_subprocess,
    set_env_var,
)
from typing_extensions import ParamSpec

from errors import SubprocessError

logger = logging.getLogger(__name__)


# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")


def execute_command(cmd: Sequence[str], check_exit: bool = True, **kwargs: Any) -> tuple[str, int]:
    """Execute a command on a subprocess.

    The command is executed with `subprocess.run`, additional arguments can be passed to it as
    keyword arguments. The following arguments to `subprocess.run` should not be set:
    `capture_output`, `shell`, `check`. As those arguments are used by this function.

    The output is logged if the log level of the logger is set to debug.

    Args:
        cmd: Command in a list.
        check_exit: Whether to check for non-zero exit code and raise exceptions.
        kwargs: Additional keyword arguments for the `subprocess.run` call.

    Returns:
        Output on stdout, and the exit code.

    Raises:
        SubprocessError: If `check_exit` is set and the exit code is non-zero.
    """
    result = secure_run_subprocess(cmd, **kwargs)

    if check_exit:
        try:
            result.check_returncode()
        except subprocess.CalledProcessError as err:
            logger.error(
                "Command %s failed with code %i: %s",
                " ".join(cmd),
                err.returncode,
                err.stderr,
            )

            raise SubprocessError(cmd, err.returncode, err.stdout, err.stderr) from err

    if isinstance(result.stdout, str):
        return (result.stdout, result.returncode)

    return (result.stdout.decode(kwargs.get("encoding", "utf-8")), result.returncode)


def get_env_var(env_var: str) -> Optional[str]:
    """Get the environment variable value.

    Looks for all upper-case and all low-case of the `env_var`.

    Args:
        env_var: Name of the environment variable.

    Returns:
        Value of the environment variable. None if not found.
    """
    return os.environ.get(env_var.upper(), os.environ.get(env_var.lower(), None))


# This is a workaround for https://bugs.launchpad.net/juju/+bug/2058335
def remove_residual_venv_dirs() -> None:  # pragma: no cover
    """Remove the residual empty directories from last revision if it exists."""
    unit_name = os.environ.get("JUJU_UNIT_NAME", "").replace("/", "-")
    if not unit_name:
        return
    venv_dir = pathlib.Path(f"/var/lib/juju/agents/unit-{unit_name}/charm/venv/")
    if not venv_dir.exists():
        return
    for path in venv_dir.iterdir():
        if path.is_dir() and not os.listdir(path):
            logger.warning("Removing residual empty dir: %s", path)
            path.rmdir()
