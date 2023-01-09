import logging
import time
from typing import Callable, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

# Return type of decorated function
R = TypeVar("R")


def retry(
    fn: Callable[..., R],
    exception: Type[Exception] = Exception,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    logger: logging.Logger = logger,
) -> Callable[..., R]:
    """Decorator for adding retry to functions.

    Args:
        fn (Callable[..., ReturnType]): Function to be decorated.
        exception (Type[Exception], optional): Exception type to be retried. Defaults to Exception.
        tries (int, optional): Number of attempts at retry. Defaults to 1.
        delay (float, optional): Time in seconds to wait between retry. Defaults to 0.
        max_delay (float, optional): Max time in seconds to wait between retry. Defaults to None.
        backoff (float, optional): Factor to increase the delay by each retry. Defaults to 1.
        logger (logging.Logger, optional): Logger for logging. Defaults to module logger.

    Returns:
        Callable[..., ReturnType]: The function decorated with retry.

    TODO:
    For Python 3.10+, PEP 612 allows to specify the parameter of callable to be the same for `fn`
    and `retry` using `ParamSpec`. Do this when focal (Python 3.8) is no longer supported.
    """

    def fn_with_retry(*args, **kwargs) -> R:
        remain_tries, current_delay = tries, delay

        while True:
            try:
                return fn(*args, **kwargs)
            except exception as err:
                remain_tries -= 1

                if remain_tries == 0:
                    if logger is not None:
                        logger.error("Retry limit of %s exceed: %s", tries)
                    raise

                if logger is not None:
                    logger.warning("Retrying error in %s seconds: %s", current_delay, err)

                time.sleep(current_delay)

                current_delay *= backoff

                if max_delay is not None:
                    current_delay = min(current_delay, max_delay)

    return fn_with_retry
