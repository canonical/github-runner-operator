# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities used by the charm."""

import functools
import logging
import os
import subprocess  # nosec B404
import time
from typing import Callable, Optional, Sequence, Type, TypeVar

from typing_extensions import ParamSpec

from errors import SubprocessError

logger = logging.getLogger(__name__)


# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")


# This decorator has default arguments, one extra argument is not a problem.
def retry(  # pylint: disable=too-many-arguments
    exception: Type[Exception] = Exception,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    local_logger: logging.Logger = logger,
) -> Callable[[Callable[ParamT, ReturnT]], Callable[ParamT, ReturnT]]:
    """Parameterize the decorator for adding retry to functions.

    Args:
        exception: Exception type to be retried.
        tries: Number of attempts at retry.
        delay: Time in seconds to wait between retry.
        max_delay: Max time in seconds to wait between retry.
        backoff: Factor to increase the delay by each retry.
        logger: Logger for logging.

    Returns:
        The function decorator for retry.
    """

    def retry_decorator(
        func: Callable[ParamT, ReturnT],
    ) -> Callable[ParamT, ReturnT]:
        """Decorate function with retry.

        Args:
            fn: The function to decorate.

        Returns:
            The resulting function with retry added.
        """

        @functools.wraps(func)
        def fn_with_retry(*args, **kwargs) -> ReturnT:
            """Wrap the function with retries."""
            remain_tries, current_delay = tries, delay

            for _ in range(tries):
                try:
                    return func(*args, **kwargs)
                # Error caught is set by the input of the function.
                except exception as err:  # pylint: disable=broad-exception-caught
                    remain_tries -= 1

                    if remain_tries == 0:
                        if local_logger is not None:
                            local_logger.exception("Retry limit of %s exceed: %s", tries, err)
                        raise

                    if local_logger is not None:
                        local_logger.warning(
                            "Retrying error in %s seconds: %s", current_delay, err
                        )
                        local_logger.debug("Error to be retried:", stack_info=True)

                    time.sleep(current_delay)

                    current_delay *= backoff

                    if max_delay is not None:
                        current_delay = min(current_delay, max_delay)

            raise RuntimeError("Unreachable code of retry logic.")

        return fn_with_retry

    return retry_decorator


def secure_run_subprocess(cmd: Sequence[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
    """Run command in subprocess according to security recommendations.

    The argument `shell` is set to `False` for security reasons.

    The argument `check` is set to `False`, therefore, CalledProcessError will not be raised.
    Errors are handled by the caller by checking the exit code.

    Args:
        cmd: Command in a list.
        kwargs: Additional keyword arguments for the `subprocess.run` call.

    Returns:
        Object representing the completed process. The outputs subprocess can accessed.
    """
    logger.info("Executing command %s", cmd)
    result = subprocess.run(  # nosec B603
        cmd,
        capture_output=True,
        shell=False,
        check=False,
        # Disable type check due to the support for unpacking arguments in mypy is experimental.
        **kwargs,  # type: ignore
    )
    logger.debug("Command %s returns: %s", cmd, result.stdout)
    return result


def execute_command(cmd: Sequence[str], check_exit: bool = True, **kwargs) -> str:
    """Execute a command on a subprocess.

    The command is executed with `subprocess.run`, additional arguments can be passed to it as
    keyword arguments. The following arguments to `subprocess.run` should not be set:
    `capture_output`, `shell`, `check`. As those arguments are used by this function.

    Args:
        cmd: Command in a list.
        check_exit: Whether to check for non-zero exit code and raise exceptions.
        kwargs: Additional keyword arguments for the `subprocess.run` call.

    Returns:
        Output on stdout.
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

    return str(result.stdout)


def get_env_var(env_var: str) -> Optional[str]:
    """Get the environment variable value.

    Looks for all upper-case and all low-case of the `env_var`.

    Args:
        env_var: Name of the environment variable.

    Returns:
        Value of the environment variable. None if not found.
    """
    return os.environ.get(env_var.upper(), os.environ.get(env_var.lower(), None))


def set_env_var(env_var: str, value: str) -> None:
    """Set the environment variable value.

    Set the all upper case and all low case of the `env_var`.

    Args:
        env_var: Name of the environment variable.
        value: Value to set environment variable to.
    """
    os.environ[env_var.upper()] = value
    os.environ[env_var.lower()] = value


def bytes_with_unit_to_kib(num_bytes: str) -> int:
    """Convert a positive integer followed by a unit to number of kibibytes.

    Args:
        num_bytes: A positive integer followed by one of the following unit: KiB, MiB, GiB, TiB,
            PiB, EiB.
    Returns:
        Number of kilobytes.
    """
    num_of_kib = {
        "KiB": 1024**0,
        "MiB": 1024**1,
        "GiB": 1024**2,
        "TiB": 1024**3,
        "PiB": 1024**4,
        "EiB": 1024**5,
    }

    num = num_bytes[:-3]
    unit = num_bytes[-3:]
    if unit in num_of_kib:
        return num_of_kib[unit] * int(num)
    else:
        raise ValueError(
            "Must be a positive integer followed by a unit",
        )
