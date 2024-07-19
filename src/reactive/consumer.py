#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for consuming jobs from the message queue."""
import logging
from contextlib import closing
from typing import cast

from kombu import Connection
from kombu.simple import SimpleQueue
from pydantic import BaseModel, HttpUrl, ValidationError

logger = logging.getLogger(__name__)


class _JobDetails(BaseModel):
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
            msg = simple_queue.get(block=True)
            try:
                job_details = cast(_JobDetails, _JobDetails.parse_raw(msg.payload))
            except ValidationError as exc:
                msg.reject(requeue=True)
                raise JobError(f"Invalid job details: {msg.payload}") from exc
            logger.info(
                "Received job with labels %s and run_url %s",
                job_details.labels,
                job_details.run_url,
            )
            msg.ack()
