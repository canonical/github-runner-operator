# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for threads."""

import logging
from queue import Queue
from threading import Thread
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _add_err_queue(function: Callable, err_queue: Queue) -> Callable:
    """Add catching exception in error queue for the function.

    Args:
        function: The function to execute and catch exceptions from.
        err_queue: The queue to send the error to.

    Returns:
        The function with exceptions send to the error queue.
    """

    def func_with_err_queue() -> None:
        """Decorate the function with send errors to queue."""
        try:
            function()
        # All possible type of exception is caught and then handled in another thread.
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.exception("Caught exception in thread")
            err_queue.put(err, block=True, timeout=None)

    return func_with_err_queue


class ThreadManager:
    """Manage a group of threads."""

    def __init__(self) -> None:
        """Construct the object."""
        self.err_queue: Queue[type[Exception]] = Queue()
        self.threads: list[Thread] = []

    def add_thread(self, target: Callable, **kwargs: Any) -> None:
        """Add a thread.

        The thread will not execute until the `start` is called.
        The implementation uses a threading.Thread object for each thread.

        Args:
            target: The function for the thread to execute.
            kwargs: Any other keyword arguments to pass to the Thread object.
        """
        func_with_err_handling = _add_err_queue(target, self.err_queue)
        thread = Thread(target=func_with_err_handling, **kwargs)
        self.threads.append(thread)

    def start(self) -> None:
        """Start execution on all threads."""
        for thread in self.threads:
            thread.start()

    def raise_on_error(self) -> None:
        """Wait until and error has occur on any thread and raise it.

        Raises:
            exception: The unhandled exception raised in a thread.
        """
        exception: type[Exception] = self.err_queue.get(block=True, timeout=None)
        raise exception
