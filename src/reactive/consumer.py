#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for consuming jobs from the message queue."""
import contextlib
import logging
import signal
import sys
from contextlib import closing
from types import FrameType
from typing import Generator, cast

from kombu import Connection
from kombu.simple import SimpleQueue
from pydantic import BaseModel, HttpUrl, ValidationError

logger = logging.getLogger(__name__)


class JobDetails(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        run_url: The URL of the job.
    """

    labels: list[str]
    run_url: HttpUrl


class JobError(Exception):
    """Raised when a job error occurs."""


def consume(mongodb_uri: str, queue_name: str) -> None:
    """Consume a job from the message queue.

    Log the job details and acknowledge the message.
    If the job details are invalid, reject the message and raise an error.

    Args:
        mongodb_uri: The URI of the MongoDB database.
        queue_name: The name of the queue.

    Raises:
        JobError: If the job details are invalid.
    """
    with Connection(mongodb_uri) as conn:
        with closing(SimpleQueue(conn, queue_name)) as simple_queue:
            with signal_handler(signal.SIGTERM):
                msg = simple_queue.get(block=True)
                try:
                    job_details = cast(JobDetails, JobDetails.parse_raw(msg.payload))
                except ValidationError as exc:
                    msg.reject(requeue=True)
                    raise JobError(f"Invalid job details: {msg.payload}") from exc
                logger.info(
                    "Received job with labels %s and run_url %s",
                    job_details.labels,
                    job_details.run_url,
                )
                msg.ack()


@contextlib.contextmanager
def signal_handler(signal_code: signal.Signals) -> Generator[None, None, None]:
    """Set a signal handler and after the context, restore the default handler.

    The signal handler exits the process.

    Args:
        signal_code: The signal code to handle.
    """
    _set_signal_handler(signal_code)
    try:
        yield
    finally:
        _restore_signal_handler(signal_code)


def _set_signal_handler(signal_code: signal.Signals) -> None:
    """Set a signal handler which exits the process.

    Args:
        signal_code: The signal code to handle.
    """

    def sigterm_handler(signal_code: int, _: FrameType | None) -> None:
        """Handle a signal.

        Call sys.exit with the signal code. Kombu should automatically
        requeue unacknowledged messages.

        Args:
            signal_code: The signal code to handle.
        """
        print(
            f"Signal '{signal.strsignal(signal_code)}' received. Will terminate.", file=sys.stderr
        )
        sys.exit(signal_code)

    signal.signal(signal_code, sigterm_handler)


def _restore_signal_handler(signal_code: signal.Signals) -> None:
    """Restore the default signal handler.

    Args:
        signal_code: The signal code to restore.
    """
    signal.signal(signal_code, signal.SIG_DFL)
