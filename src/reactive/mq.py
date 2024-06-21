#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for MQ communication."""
from kombu import Connection

from reactive import Job


class InactiveMQError(Exception):
    """Raised when the connection to the MQ is inactive."""
    pass


class Message:
    """A message from the MQ. The close method should be called after the message is processed.

    Consider using `contextlib.closing` to ensure the resources are closed.
    """

    def __init__(self, connection: Connection, queue_name: str):
        """Initialize the message.

        Args:
            connection: The connection to the MQ.
            queue_name: The name of the queue.
        """

    def get_job(self) -> Job:
        """Get the job from the message.

        Returns:
            The consumed job.

        Raises:
            InactiveMQError: If the connection to the MQ is inactive
                (e.g. has already been closed or processed).
        """

    def reject(self) -> None:
        """Do not acknowledge and requeue the message.

        Raises:
            InactiveMQError: If the connection to the MQ is inactive
                (e.g. has already been closed or processed).
        """

    def ack(self) -> None:
        """Acknowledge the message.

        Raises:
            InactiveMQError: If the connection to the MQ is inactive
                (e.g. has already been closed or processed).
        """

    def close(self) -> None:
        """Close the connection and the queue resources.

        Raises:
            InactiveMQError: If the connection to the MQ is inactive
                (e.g. has already been closed or processed).
        """


def consume(mq_uri: str, queue_name: str) -> Message:
    """Consume a messages from the MQ.

    Args:
        mq_uri: The URI of the MQ.
        queue_name: The name of the queue.

    Returns:
        The consumed message.
    """
