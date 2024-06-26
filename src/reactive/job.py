#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for job retrieval and handling."""

from typing import Protocol

from pydantic import AnyUrl, BaseModel, HttpUrl


class MessageQueueConnectionInfo(BaseModel):
    """The connection information for the MQ."""

    uri: AnyUrl
    queue_name: str


class JobSourceError(Exception):
    """Raised when a job source error occurs."""


class JobSource(Protocol):
    """A protocol for a job source."""

    def ack(self) -> None:
        """Acknowledge the message.

        Raises:
            JobSourceError: If the job could not be acknowledged.
        """

    def reject(self) -> None:
        """Reject the message.

        Raises:
            JobSourceError: If the job could not be rejected.
        """


class JobError(Exception):
    """Raised when a job error occurs."""


class Job:
    """A class to represent a job to be picked up by a runner."""

    def __init__(self, job_source: JobSource):
        """Initialize the message.

        Args:
            job_source: The source of the job.
        """

    @property
    def labels(self) -> list[str]:
        """The labels of the job.

        Returns:
            The labels of the job.
        """

    @property
    def run_url(self) -> HttpUrl:
        """The GitHub run URL of the job.

        Returns:
            The GitHub run URL of the job.
        """

    def reject(self) -> None:
        """Mark the job as rejected.

        Raises:
            JobError: If the job could not be rejected.
        """

    def picked_up(self) -> None:
        """Indicate that the job has been picked up by a runner.

        Raises:
            JobError: If the job could not be acknowledged.
        """

    @staticmethod
    def from_message_queue(mq_connection_info: MessageQueueConnectionInfo) -> "Job":
        """Get a job from a message queue.

        This method will block until a job is available.

        Args:
            mq_connection_info: The connection information for the MQ.

        Returns:
            The retrieved Job.
        """
