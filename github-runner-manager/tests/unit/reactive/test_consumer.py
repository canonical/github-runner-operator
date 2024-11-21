#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

import secrets
from contextlib import closing
from datetime import datetime, timezone
from random import randint
from unittest.mock import MagicMock

import pytest
from kombu import Connection, Message
from kombu.exceptions import KombuError

from github_runner_manager.reactive import consumer
from github_runner_manager.reactive.consumer import JobError, Labels, get_queue_size
from github_runner_manager.reactive.types_ import QueueConfig
from github_runner_manager.types_.github import JobConclusion, JobInfo, JobStatus

IN_MEMORY_URI = "memory://"
FAKE_JOB_URL = "https://api.github.com/repos/fakeuser/gh-runner-test/actions/runs/8200803099"


@pytest.fixture(name="queue_config")
def queue_config_fixture() -> QueueConfig:
    """Return a QueueConfig object."""
    queue_name = secrets.token_hex(16)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    return QueueConfig.construct(mongodb_uri=IN_MEMORY_URI, queue_name=queue_name)


@pytest.fixture(name="mock_sleep", autouse=True)
def mock_sleep_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the sleep function."""
    monkeypatch.setattr(consumer, "sleep", lambda _: None)


@pytest.mark.parametrize(
    "labels,supported_labels",
    [
        pytest.param({"label1", "label2"}, {"label1", "label2"}, id="label==supported_labels"),
        pytest.param(set(), {"label1", "label2"}, id="empty labels"),
        pytest.param({"label1"}, {"label1", "label3"}, id="labels subset of supported_labels"),
        pytest.param({"LaBeL1", "label2"}, {"label1", "laBeL2"}, id="case insensitive labels"),
    ],
)
def test_consume(labels: Labels, supported_labels: Labels, queue_config: QueueConfig):
    """
    arrange: A job with valid labels placed in the message queue which has not yet been picked up.
    act: Call consume.
    assert: A runner is created and the message is removed from the queue.
    """
    job_details = consumer.JobDetails(
        labels=labels,
        url=FAKE_JOB_URL,
    )
    _put_in_queue(job_details.json(), queue_config.queue_name)

    runner_manager_mock = MagicMock(spec=consumer.RunnerManager)
    github_client_mock = MagicMock(spec=consumer.GithubClient)
    github_client_mock.get_job_info.side_effect = [
        _create_job_info(JobStatus.QUEUED),
        _create_job_info(JobStatus.IN_PROGRESS),
    ]

    consumer.consume(
        queue_config=queue_config,
        runner_manager=runner_manager_mock,
        github_client=github_client_mock,
        supported_labels=supported_labels,
    )

    runner_manager_mock.create_runners.assert_called_once_with(1)

    _assert_queue_is_empty(queue_config.queue_name)


def test_consume_reject_if_job_gets_not_picked_up(queue_config: QueueConfig):
    """
    arrange: A job placed in the message queue which will not get picked up.
    act: Call consume.
    assert: The message is requeued.
    """
    labels = {secrets.token_hex(16), secrets.token_hex(16)}
    job_details = consumer.JobDetails(
        labels=labels,
        url=FAKE_JOB_URL,
    )
    _put_in_queue(job_details.json(), queue_config.queue_name)

    runner_manager_mock = MagicMock(spec=consumer.RunnerManager)
    github_client_mock = MagicMock(spec=consumer.GithubClient)
    github_client_mock.get_job_info.return_value = _create_job_info(JobStatus.QUEUED)

    consumer.consume(
        queue_config=queue_config,
        runner_manager=runner_manager_mock,
        github_client=github_client_mock,
        supported_labels=labels,
    )

    _assert_msg_has_been_requeued(queue_config.queue_name, job_details.json())


def test_consume_reject_if_spawning_failed(queue_config: QueueConfig):
    """
    arrange: A job placed in the message queue and spawning a runner fails.
    act: Call consume.
    assert: The message is requeued.
    """
    labels = {secrets.token_hex(16), secrets.token_hex(16)}
    job_details = consumer.JobDetails(
        labels=labels,
        url=FAKE_JOB_URL,
    )
    _put_in_queue(job_details.json(), queue_config.queue_name)

    runner_manager_mock = MagicMock(spec=consumer.RunnerManager)
    runner_manager_mock.create_runners.return_value = tuple()

    github_client_mock = MagicMock(spec=consumer.GithubClient)
    github_client_mock.get_job_info.return_value = _create_job_info(JobStatus.QUEUED)

    consumer.consume(
        queue_config=queue_config,
        runner_manager=runner_manager_mock,
        github_client=github_client_mock,
        supported_labels=labels,
    )

    _assert_msg_has_been_requeued(queue_config.queue_name, job_details.json())


def test_consume_raises_queue_error(monkeypatch: pytest.MonkeyPatch, queue_config: QueueConfig):
    """
    arrange: A mocked SimpleQueue that raises a KombuError.
    act: Call consume.
    assert: A QueueError is raised.
    """
    monkeypatch.setattr(consumer, "SimpleQueue", MagicMock(side_effect=KombuError))
    with pytest.raises(consumer.QueueError) as exc_info:
        consumer.consume(
            queue_config=queue_config,
            runner_manager=MagicMock(spec=consumer.RunnerManager),
            github_client=MagicMock(spec=consumer.GithubClient),
            supported_labels={"label1", "label2"},
        )
    assert "Error when communicating with the queue" in str(exc_info.value)


@pytest.mark.parametrize(
    "size",
    [
        pytest.param(0, id="empty queue"),
        pytest.param(1, id="queue with 1 item"),
        pytest.param(randint(2, 10), id="queue with multiple items"),
    ],
)
def test_get_queue_size(size: int, queue_config: QueueConfig):
    """
    arrange: A queue with a given size.
    act: Call get_queue_size.
    assert: The size of the queue is returned.
    """
    for _ in range(size):
        _put_in_queue("test", queue_config.queue_name)
    assert get_queue_size(queue_config) == size


def test_get_queue_size_raises_queue_error(
    monkeypatch: pytest.MonkeyPatch, queue_config: QueueConfig
):
    """
    arrange: A queue with a given size and a mocked SimpleQueue that raises a KombuError.
    act: Call get_queue_size.
    assert: A QueueError is raised.
    """
    monkeypatch.setattr(consumer, "SimpleQueue", MagicMock(side_effect=KombuError))
    with pytest.raises(consumer.QueueError) as exc_info:
        get_queue_size(queue_config)
    assert "Error when communicating with the queue" in str(exc_info.value)


@pytest.mark.parametrize(
    "job_str",
    [
        pytest.param(
            '{"labels": ["label1", "label2"], "status": "completed"}', id="job url missing"
        ),
        pytest.param(
            '{"status": "completed", "url": "https://example.com/path"}', id="labels missing"
        ),
        pytest.param(
            '{"labels": ["label1", "label2"], "status": "completed", '
            '"url": "https://example.com"}',
            id="job url without path",
        ),
        pytest.param("no json at all", id="invalid json"),
    ],
)
def test_job_details_validation_error(job_str: str, queue_config: QueueConfig):
    """
    arrange: A job placed in the message queue with invalid details.
    act: Call consume
    assert: A JobError is raised and the message is not requeued.
    """
    queue_name = queue_config.queue_name
    _put_in_queue(job_str, queue_name)

    runner_manager_mock = MagicMock(spec=consumer.RunnerManager)
    github_client_mock = MagicMock(spec=consumer.GithubClient)
    github_client_mock.get_job_info.return_value = _create_job_info(JobStatus.IN_PROGRESS)

    with pytest.raises(JobError) as exc_info:
        consumer.consume(
            queue_config=queue_config,
            runner_manager=runner_manager_mock,
            github_client=github_client_mock,
            supported_labels={"label1", "label2"},
        )
    assert "Invalid job details" in str(exc_info.value)

    _assert_queue_is_empty(queue_config.queue_name)


@pytest.mark.parametrize(
    "labels,supported_labels",
    [
        pytest.param({"label1", "unsupported"}, {"label1"}, id="additional unsupported label"),
        pytest.param({"label1"}, set(), id="empty supported labels"),
        pytest.param({"label1", "label2"}, {"label1", "label3"}, id="overlapping labels"),
        pytest.param({"label1", "label2"}, {"label3", "label4"}, id="no overlap"),
        pytest.param({"LaBeL1", "label2"}, {"label1", "laBeL3"}, id="case insensitive labels"),
    ],
)
def test_consume_reject_if_labels_not_supported(
    labels: Labels, supported_labels: Labels, queue_config: QueueConfig
):
    """
    arrange: A job placed in the message queue with unsupported labels.
    act: Call consume.
    assert: No runner is spawned and the message is removed from the queue.
    """
    job_details = consumer.JobDetails(
        labels=labels,
        url=FAKE_JOB_URL,
    )
    _put_in_queue(job_details.json(), queue_config.queue_name)

    runner_manager_mock = MagicMock(spec=consumer.RunnerManager)
    github_client_mock = MagicMock(spec=consumer.GithubClient)
    github_client_mock.get_job_info.side_effect = [
        _create_job_info(JobStatus.QUEUED),
        _create_job_info(JobStatus.IN_PROGRESS),
    ]

    consumer.consume(
        queue_config=queue_config,
        runner_manager=runner_manager_mock,
        github_client=github_client_mock,
        supported_labels=supported_labels,
    )

    runner_manager_mock.create_runners.assert_not_called()
    _assert_queue_is_empty(queue_config.queue_name)


def _create_job_info(status: JobStatus) -> JobInfo:
    """Create a JobInfo object with the given status.

    Args:
        status: The status of the job.

    Returns:
        The JobInfo object.
    """
    return JobInfo(
        created_at=datetime(2021, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2021, 10, 1, 1, 0, 0, tzinfo=timezone.utc),
        conclusion=JobConclusion.SUCCESS,
        status=status,
        job_id=randint(1, 1000),
    )


def _put_in_queue(msg: str, queue_name: str) -> None:
    """Put a job in the message queue.

    Args:
        msg: The job details.
        queue_name: The name of the queue
    """
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(msg, retry=True)


def _consume_from_queue(queue_name: str) -> Message:
    """Consume a job from the message queue.

    Args:
        queue_name: The name of the queue

    Returns:
        The message consumed from the queue.
    """
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            return simple_queue.get(block=False)


def _assert_queue_is_empty(queue_name: str) -> None:
    """Assert that the queue is empty.

    Args:
        queue_name: The name of the queue.
    """
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            assert simple_queue.qsize() == 0


def _assert_msg_has_been_requeued(queue_name: str, payload: str) -> None:
    """Assert that the message is requeued.

    This will consume message from the queue and assert that the payload is the same as the given.

    Args:
        queue_name: The name of the queue.
        payload: The payload of the message to assert.
    """
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            assert simple_queue.get(block=False).payload == payload
