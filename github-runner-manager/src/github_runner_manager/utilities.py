# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities used by the charm."""

import functools
import logging
import os
import subprocess  # nosec B404
import time
from typing import Any, Callable, Optional, Sequence, Type, TypeVar

from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)


# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")


# This decorator has default arguments, one extra argument is not a problem.
def retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
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
        local_logger: Logger for logging.

    Returns:
        The function decorator for retry.
    """

    def retry_decorator(
        func: Callable[ParamT, ReturnT],
    ) -> Callable[ParamT, ReturnT]:
        """Decorate function with retry.

        Args:
            func: The function to decorate.

        Returns:
            The resulting function with retry added.
        """

        @functools.wraps(func)
        def fn_with_retry(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
            """Wrap the function with retries.

            Args:
                args: The placeholder for decorated function's positional arguments.
                kwargs: The placeholder for decorated function's key word arguments.

            Raises:
                RuntimeError: Should be unreachable.

            Returns:
                Original return type of the decorated function.
            """
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


def secure_run_subprocess(
    cmd: Sequence[str], hide_cmd: bool = False, **kwargs: dict[str, Any]
) -> subprocess.CompletedProcess[bytes]:
    """Run command in subprocess according to security recommendations.

    CalledProcessError will not be raised on error of the command executed.
    Errors should be handled by the caller by checking the exit code.

    The command is executed with `subprocess.run`, additional arguments can be passed to it as
    keyword arguments. The following arguments to `subprocess.run` should not be set:
    `capture_output`, `shell`, `check`. As those arguments are used by this function.

    Args:
        cmd: Command in a list.
        hide_cmd: Hide logging of cmd.
        kwargs: Additional keyword arguments for the `subprocess.run` call.

    Returns:
        Object representing the completed process. The outputs subprocess can accessed.
    """
    if not hide_cmd:
        logger.info("Executing command %s", cmd)
    else:
        logger.info("Executing sensitive command")

    result = subprocess.run(  # nosec B603
        cmd,
        capture_output=True,
        # Not running in shell to avoid security problems.
        shell=False,
        check=False,
        # Disable type check due to the support for unpacking arguments in mypy is experimental.
        **kwargs,  # type: ignore
    )
    if not hide_cmd:
        logger.debug("Command %s returns: %s", cmd, result.stdout)
    else:
        logger.debug("Command returns: %s", result.stdout)
    return result


def set_env_var(env_var: str, value: str) -> None:
    """Set the environment variable value.

    Set the all upper case and all low case of the `env_var`.

    Args:
        env_var: Name of the environment variable.
        value: Value to set environment variable to.
    """
    os.environ[env_var.upper()] = value
    os.environ[env_var.lower()] = value
