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

logger = logging.getLogger(__name__)


# Parameters of the function decorated with retry
TParam = ParamSpec("TParam")
# Return type of the function decorated with retry
TReturn = TypeVar("TReturn")


def retry(
    exception: Type[Exception] = Exception,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    logger: logging.Logger = logger,
) -> Callable[[Callable[TParam, TReturn]], Callable[TParam, TReturn]]:
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
        fn: Callable[TParam, TReturn],
    ) -> Callable[TParam, TReturn]:
        """Decorate function with retry.

        Args:
            fn (Callable[..., R]): The function to decorate.

        Returns:
            Callable[..., R]: The resulting function with retry added.
        """

        @functools.wraps(fn)
        def fn_with_retry(*args, **kwargs) -> TReturn:
            """Wrap the function with retries."""
            remain_tries, current_delay = tries, delay

            for _ in range(tries):
                try:
                    return fn(*args, **kwargs)
                except exception as err:
                    remain_tries -= 1

                    if remain_tries == 0:
                        if logger is not None:
                            logger.exception("Retry limit of %s exceed: %s", tries, err)
                        raise

                    if logger is not None:
                        logger.warning("Retrying error in %s seconds: %s", current_delay, err)
                        logger.debug("Error to be retried:", stack_info=True)

                    time.sleep(current_delay)

                    current_delay *= backoff

                    if max_delay is not None:
                        current_delay = min(current_delay, max_delay)

            raise RuntimeError("Unreachable code of retry logic.")

        return fn_with_retry

    return retry_decorator


def execute_command(cmd: Sequence[str], check: bool = True) -> str:
    """Execute a command on a subprocess.

    Args:
        cmd: Command in a list.
        check: Whether to throw error on non-zero exit code.

    Returns:
        Output on stdout.

    TODO:
        Update `event_timer.py` to use this function.
    """
    logger.info("Executing command %s", cmd)
    result = subprocess.run(cmd, capture_output=True)  # nosec B603
    logger.debug("Command %s returns: %s", cmd, result.stdout)

    if check:
        try:
            result.check_returncode()
        except subprocess.CalledProcessError as err:
            logger.error(
                "Command %s failed with code %i: %s",
                " ".join(cmd),
                err.returncode,
                err.stderr,
            )
            raise

    return str(result.stdout)


def get_env_var(env_var: str) -> Optional[str]:
    """Get the environment variable value.

    Looks for all upper-case and all low-case of the `env_var`.

    Args:
        env_var: Name of environment variable.

    Returns:
        Value of the environment variable. None if not found.
    """
    return os.environ.get(env_var.upper(), os.environ.get(env_var.lower(), None))
