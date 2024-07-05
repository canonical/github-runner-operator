#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for job retrieval and handling."""

from typing import Protocol, cast

from kombu import Connection, Message
from kombu.exceptions import MessageStateError
from kombu.simple import SimpleQueue
from pydantic import AnyUrl, BaseModel, HttpUrl

# TODO: add sigterm handler to requeue the message if the process is killed


class JobDetails(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        run_url: The URL of the job.
    """

    labels: list[str]
    run_url: HttpUrl


class MessageQueueConnectionInfo(BaseModel):
    """The connection information for the MQ.

    Attributes:
        uri: The URI of the MQ.
        queue_name: The name of the queue.
    """

    uri: AnyUrl
    queue_name: str


class JobSourceError(Exception):
    """Raised when a job source error occurs."""


class JobSource(Protocol):
    """A protocol for a job source."""

    def ack(self) -> None:
        """Acknowledge the message."""

    def reject(self) -> None:
        """Reject the message."""

    def get_job(self) -> JobDetails:
        """Get the job details from the source."""


class _MQJobSource(JobSource):
    """A class to represent a job source from a message queue."""

    def __init__(self, conn: Connection, queue: SimpleQueue, msg: Message):
        """Initialize the message.

        Args:
            conn: The connection to the message queue.
            queue: The queue to get the message from.
            msg: The message to get the job details from.
        """
        self._conn = conn
        self._queue = queue
        self._msg = msg

    def ack(self) -> None:
        """Acknowledge the message.

        This will ensure that the message is removed from the queue.
        The connection will also be closed, this method is expected to only be called once.

        Raises:
            JobSourceError: If the message could not be acknowledged.
        """
        try:
            self._msg.ack()
        except MessageStateError as e:
            raise JobSourceError("Could not acknowledge message") from e
        self._close()

    def reject(self) -> None:
        """Reject the message.

        This will ensure that the message is requeued.
        The connection will also be closed, this method is expected to only be called once.

        Raises:
            JobSourceError: If the message could not be rejected.
        """
        try:
            self._msg.reject(requeue=True)
        except MessageStateError as e:
            raise JobSourceError("Could not reject message") from e
        self._close()

    def get_job(self) -> JobDetails:
        """Get the job details from the message.

        Raises:
            JobSourceError: If the job details could not be retrieved.

        Returns:
            The job details.
        """
        try:
            return cast(JobDetails, JobDetails.parse_raw(self._msg.payload))
        except ValueError as e:
            raise JobSourceError("Could not parse job details") from e

    def _close(self) -> None:
        """Close the connection and the queue."""
        self._queue.close()
        self._conn.close()


class JobError(Exception):
    """Raised when a job error occurs."""


class Job:
    """A class to represent a job to be picked up by a runner."""

    def __init__(self, job_source: JobSource):
        """Initialize the message.

        Args:
            job_source: The source of the job.
        """
        self._job_source = job_source

    def get_details(self) -> JobDetails:
        """Get the job details.

        Raises:
            JobError: If the job details could not be retrieved.

        Returns:
            The job details.
        """
        try:
            return self._job_source.get_job()
        except JobSourceError as e:
            raise JobError("Could not get job details") from e

    def reject(self) -> None:
        """Mark the job as rejected.

        Raises:
            JobError: If the job could not be rejected.
        """
        try:
            self._job_source.reject()
        except JobSourceError as e:
            raise JobError("Could not reject job") from e

    def picked_up(self) -> None:
        """Indicate that the job has been picked up by a runner.

        Raises:
            JobError: If the job could not be acknowledged.
        """
        try:
            self._job_source.ack()
        except JobSourceError as e:
            raise JobError("Could not acknowledge job") from e

    @staticmethod
    def from_message_queue(mq_connection_info: MessageQueueConnectionInfo) -> "Job":
        """Get a job from a message queue.

        This method will block until a job is available.

        Args:
            mq_connection_info: The connection information for the MQ.

        Returns:
            The retrieved Job.
        """
        conn = Connection(mq_connection_info.uri)

        simple_queue = conn.SimpleQueue(mq_connection_info.queue_name)

        # TODO: add timeout
        msg = simple_queue.get(block=True)
        mq_job_source = _MQJobSource(conn, simple_queue, msg)

        return Job(mq_job_source)
