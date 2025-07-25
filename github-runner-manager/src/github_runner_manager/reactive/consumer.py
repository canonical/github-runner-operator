#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for consuming jobs from the message queue."""
import contextlib
import logging
import re
import signal
import sys
from contextlib import closing
from time import sleep
from types import FrameType
from typing import Generator, cast
from urllib.parse import urlparse

from kombu import Connection, Message
from kombu.exceptions import KombuError
from kombu.simple import SimpleQueue
from pydantic import BaseModel, HttpUrl, ValidationError, validator

from github_runner_manager.manager.models import RunnerMetadata
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.platform.platform_provider import JobNotFoundError, PlatformProvider
from github_runner_manager.reactive.types_ import QueueConfig

logger = logging.getLogger(__name__)

Labels = set[str]

PROCESS_COUNT_HEADER_NAME = "X-Process-Count"
WAIT_TIME_IN_SEC = 60
RETRY_LIMIT = 5
# This control message is for testing. The reactive process will stop consuming messages
# when the message is sent. This message does not come from the router.
END_PROCESSING_PAYLOAD = "__END__"


class JobDetails(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        url: The URL of the job to check its status.
    """

    labels: Labels
    url: HttpUrl

    @validator("url")
    @classmethod
    def check_job_url_path_is_not_empty(cls, v: HttpUrl) -> HttpUrl:
        """Check that the job_url path is not empty.

        Args:
            v: The job_url to check.

        Returns:
            The job_url if it is valid.

        Raises:
            ValueError: If the job_url path is empty.
        """
        if not v.path:
            raise ValueError("path must be provided")
        return v


class JobError(Exception):
    """Raised when a job error occurs."""


class QueueError(Exception):
    """Raised when an error when communicating with the queue occurs."""


def get_queue_size(queue_config: QueueConfig) -> int:
    """Get the size of the message queue.

    Args:
        queue_config: The configuration for the message queue.

    Returns:
        The size of the queue.

    Raises:
        QueueError: If an error when communicating with the queue occurs.
    """
    try:
        with Connection(queue_config.mongodb_uri) as conn:
            with closing(SimpleQueue(conn, queue_config.queue_name)) as simple_queue:
                return simple_queue.qsize()
    except KombuError as exc:
        raise QueueError("Error when communicating with the queue") from exc


# Ignore `consume` too complex as it is pending re-design.
def consume(  # noqa: C901
    queue_config: QueueConfig,
    runner_manager: RunnerManager,
    platform_provider: PlatformProvider,
    supported_labels: Labels,
) -> None:
    """Consume a job from the message queue.

    Log the job details and acknowledge the message.
    If the job details are invalid, reject the message and raise an error.

    Args:
        queue_config: The configuration for the message queue.
        runner_manager: The runner manager used to create the runner.
        platform_provider: Platform provider.
        supported_labels: The supported labels for the runner. If the job has unsupported labels,
            the message is requeued.

    Raises:
        QueueError: If an error when communicating with the queue occurs.
    """
    try:
        with (
            Connection(queue_config.mongodb_uri) as conn,
            closing(SimpleQueue(conn, queue_config.queue_name)) as simple_queue,
            signal_handler(signal.SIGTERM),
        ):
            # Get messages until we can spawn a runner.
            while True:
                msg = simple_queue.get(block=True)
                # Payload to stop the processing
                if msg.payload == END_PROCESSING_PAYLOAD:
                    msg.ack()
                    break

                msg.headers[PROCESS_COUNT_HEADER_NAME] = (
                    msg.headers.get(PROCESS_COUNT_HEADER_NAME, 0) + 1
                )
                msg_process_count = msg.headers[PROCESS_COUNT_HEADER_NAME]

                job_details = _parse_job_details(msg)
                logger.info("Received reactive job: %s", job_details)

                if msg_process_count > RETRY_LIMIT:
                    logger.warning(
                        "Retry limit reach for job %s with labels: %s",
                        job_details.url,
                        job_details.labels,
                    )
                    msg.reject(requeue=False)
                    continue

                if msg_process_count > 1:
                    logger.info(
                        "Pause job %s with retry count %s", job_details.url, msg_process_count
                    )
                    # Avoid rapid retrying to prevent overloading services, e.g., OpenStack API.
                    sleep(WAIT_TIME_IN_SEC)

                if not _validate_labels(
                    labels=job_details.labels, supported_labels=supported_labels
                ):
                    logger.error(
                        "Found unsupported job labels in %s. "
                        "Will not spawn a runner and reject the message.",
                        job_details.labels,
                    )
                    # We currently do not expect this to happen, but we should handle it.
                    # We do not want to requeue the message as it will be rejected again.
                    # This may change in the future when messages for multiple
                    # flavours are sent to the same queue.
                    msg.reject(requeue=False)
                    continue
                try:
                    metadata = _build_runner_metadata(job_details.url)
                except ValueError:
                    msg.reject(requeue=False)
                    break
                try:
                    if platform_provider.check_job_been_picked_up(
                        metadata=metadata, job_url=job_details.url
                    ):
                        logger.info("reactive job: %s already picked up.", job_details)
                        msg.ack()
                        continue
                except JobNotFoundError:
                    logger.warning(
                        "Unable to find the job %s. Not retrying this job.", job_details.url
                    )
                    msg.reject(requeue=False)
                _spawn_runner(
                    runner_manager=runner_manager,
                    job_url=job_details.url,
                    msg=msg,
                    platform_provider=platform_provider,
                    metadata=metadata,
                )
                break
    except KombuError as exc:
        raise QueueError("Error when communicating with the queue") from exc


def _build_runner_metadata(job_url: str) -> RunnerMetadata:
    """Build runner metadata from the job url."""
    parsed_url = urlparse(job_url)
    # We expect the netloc to contain github.com, otherwise this function will fail,
    # as will use jobmanager code to handle github runners.
    if "github.com" in parsed_url.netloc:
        return RunnerMetadata()

    # From here on jobmanager. For now we just regex on the url to check if it is the url
    # of a runner.
    match_result = re.match(r"^(.*)/v1/jobs/(\d+)$", parsed_url.path)
    if not match_result:
        logger.error("Invalid URL for a job. url: %s", job_url)
        raise ValueError(f"Invalid format for job url {job_url}")
    base_url = parsed_url._replace(path=match_result.group(1)).geturl()
    return RunnerMetadata(platform_name="jobmanager", url=base_url)


def _parse_job_details(msg: Message) -> JobDetails:
    """Parse JobDetails from a message."""
    try:
        job_details = cast(JobDetails, JobDetails.parse_raw(msg.payload))
    except ValidationError as exc:
        logger.error("Found invalid job details, will reject the message.")
        msg.reject(requeue=False)
        raise JobError(f"Invalid job details: {msg.payload}") from exc
    logger.info(
        "Received job with labels %s and job_url %s",
        job_details.labels,
        job_details.url,
    )
    return job_details


def _validate_labels(labels: Labels, supported_labels: Labels) -> bool:
    """Validate the labels of the job.

    Args:
        labels: The labels of the job.
        supported_labels: The supported labels for the runner.

    Returns:
        True if the labels are valid, False otherwise.
    """
    return {label.lower() for label in labels} <= {label.lower() for label in supported_labels}


def _spawn_runner(
    runner_manager: RunnerManager,
    job_url: HttpUrl,
    msg: Message,
    platform_provider: PlatformProvider,
    metadata: RunnerMetadata,
) -> None:
    """Spawn a runner.

    A runner is only spawned if the job has not yet been picked up by a runner.
    After spawning a runner, it is checked if the job has been picked up.

    If the job has been picked up, the message is acknowledged.
    If the job has not been picked up after 5 minutes, the message is rejected and requeued.

    Args:
        runner_manager: The runner manager to use.
        job_url: The URL of the job.
        msg: The message to acknowledge or reject.
        platform_provider: Platform provider.
        metadata: RunnerMetadata for the runner to spawn..
    """
    logger.info("Spawning new reactive runner for job %s", job_url)
    instance_ids = runner_manager.create_runners(1, metadata=metadata, reactive=True)
    if not instance_ids:
        logger.error("Failed to spawn a runner for job %s. Will reject the message.", job_url)
        msg.reject(requeue=True)
        return
    logger.info("Reactive runner spawned %s", instance_ids)

    for _ in range(5):
        sleep(WAIT_TIME_IN_SEC)
        logger.info("Checking if job picked up for reactive runner %s", instance_ids)
        if platform_provider.check_job_been_picked_up(metadata=metadata, job_url=job_url):
            logger.info("Job picked %s. reactive runner ok %s", job_url, instance_ids)
            msg.ack()
            break
    else:
        logger.info(
            "Job %s not picked by reactive runner %s. Probably picked up by another job",
            job_url,
            instance_ids,
        )
        msg.reject(requeue=True)


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
