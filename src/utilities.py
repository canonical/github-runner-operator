# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities used by the charm."""

import logging
import subprocess  # nosec B404
import time
from typing import Callable, Optional, Sequence, Type, TypeVar

logger = logging.getLogger(__name__)

# Return type of decorated function
R = TypeVar("R")


def retry(
    exception: Type[Exception] = Exception,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    logger: logging.Logger = logger,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Parameterize the decorator for adding retry to functions.

    Args:
        exception: Exception type to be retried. Defaults to Exception.
        tries: Number of attempts at retry. Defaults to 1.
        delay: Time in seconds to wait between retry. Defaults to 0.
        max_delay: Max time in seconds to wait between retry. Defaults to None.
        backoff: Factor to increase the delay by each retry. Defaults to 1.
        logger: Logger for logging. Defaults to module logger.

    Returns:
        The function decorator for retry.

    TODO:
    For Python 3.10+, PEP 612 allows to specify the parameter of callable using `ParamSpec`. Do
    this when focal (Python 3.8) is no longer supported.
    """

    def retry_decorator(
        fn: Callable[..., R],
    ) -> Callable[..., R]:
        """Decorate function with retry.

        Args:
            fn (Callable[..., R]): The function to decorate.

        Returns:
            Callable[..., R]: The resulting function with retry added.
        """

        def fn_with_retry(*args, **kwargs) -> R:
            """Function with retry"""
            remain_tries, current_delay = tries, delay

            while True:
                try:
                    return fn(*args, **kwargs)
                except exception as err:
                    remain_tries -= 1

                    if remain_tries == 0:
                        if logger is not None:
                            logger.error("Retry limit of %s exceed: %s", tries, err)
                        raise

                    if logger is not None:
                        logger.warning("Retrying error in %s seconds: %s", current_delay, err)

                    time.sleep(current_delay)

                    current_delay *= backoff

                    if max_delay is not None:
                        current_delay = min(current_delay, max_delay)

        return fn_with_retry

    return retry_decorator


def execute_command(cmd: Sequence[str], check: bool = True) -> str:
    """Execute a command on a subprocess.

    Args:
        cmd: Command in a list.
        check: Whether to throw error on non-zero exit code. Defaults to True.

    Returns:
        Output on stdout.

    TODO:
        Update `event_timer.py` to use this function.
    """
    result = subprocess.run(cmd, capture_output=True)  # nosec B603
    logger.debug("Command %s returns: %s", " ".join(cmd), result.stdout)

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
