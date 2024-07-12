#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the job module."""
import secrets
from contextlib import closing
from unittest.mock import MagicMock

import pytest
from kombu import Connection

from reactive.job import Job, JobDetails, JobError, JobSource, MessageQueueConnectionInfo

IN_MEMORY_URI = "memory://"
FAKE_RUN_URL = "https://api.github.com/repos/fakeusergh-runner-test/actions/runs/8200803099"


def test_job_from_message_queue():
    """
    arrange: A job placed in the message queue.
    act: Call Job.from_message_queue.
    assert: The job is returned and contains the expected details.
    """
    queue_name = secrets.token_hex(16)
    job_details = JobDetails(
        labels=[secrets.token_hex(16), secrets.token_hex(16)],
        run_url=FAKE_RUN_URL,
    )
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(job_details.json(), retry=True)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    mq_conn_info = MessageQueueConnectionInfo.construct(uri=IN_MEMORY_URI, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)
    assert job.get_details() == job_details


def test_reject():
    """
    arrange: A job retrieved from the message queue.
    act: Reject the job.
    assert: The job is still in the queue.
    """
    queue_name = secrets.token_hex(16)
    job_details = JobDetails(
        labels=[secrets.token_hex(16), secrets.token_hex(16)],
        run_url=FAKE_RUN_URL,
    )
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(job_details.json(), retry=True)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    mq_conn_info = MessageQueueConnectionInfo.construct(uri=IN_MEMORY_URI, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)

    job.reject()

    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            job_msg = simple_queue.get(block=True, timeout=0.01)
            assert job_msg.payload == job_details.json()


def test_reject_multiple_times_raises_error():
    """
    arrange: A job retrieved from the message queue.
    act: Reject the job twice.
    assert: The second rejection raises an error.
    """
    queue_name = secrets.token_hex(16)
    job_details = JobDetails(
        labels=[secrets.token_hex(16), secrets.token_hex(16)],
        run_url=FAKE_RUN_URL,
    )
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(job_details.json(), retry=True)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    mq_conn_info = MessageQueueConnectionInfo.construct(uri=IN_MEMORY_URI, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)

    job.reject()
    for _ in range(2):
        with pytest.raises(JobError) as exc_info:
            job.reject()
        assert "Could not reject job" in str(exc_info.value)


def test_picked_up_acknowledges_job():
    """
    arrange: A fake job source.
    act: Acknowledge the job.
    assert: The ack method of the job source is called.
    """
    fake_job_source = MagicMock(spec=JobSource)

    job = Job(fake_job_source)
    job.picked_up()

    fake_job_source.ack.assert_called_once()


def test_picked_up_multiple_times_raises_error():
    """
    arrange: A job retrieved from the message queue.
    act: Acknowledge the job twice.
    assert: The second acknowledgement raises an error.
    """
    queue_name = secrets.token_hex(16)
    job_details = JobDetails(
        labels=[secrets.token_hex(16), secrets.token_hex(16)],
        run_url=FAKE_RUN_URL,
    )
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(job_details.json(), retry=True)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    mq_conn_info = MessageQueueConnectionInfo.construct(uri=IN_MEMORY_URI, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)

    job.picked_up()
    for _ in range(2):
        with pytest.raises(JobError) as exc_info:
            job.picked_up()
        assert "Could not acknowledge job" in str(exc_info.value)


@pytest.mark.parametrize(
    "job_str",
    [
        pytest.param(
            '{"labels": ["label1", "label2"], "status": "completed"}', id="run_url missing"
        ),
        pytest.param(
            '{"status": "completed", "run_url": "https://example.com"}', id="labels missing"
        ),
        pytest.param("no json at all", id="invalid json"),
    ],
)
def test_job_details_validation_error(job_str: str):
    """
    arrange: A job placed in the message queue with invalid details.
    act: Call Job.from_message_queue.
    assert: A JobError is raised.
    """
    queue_name = secrets.token_hex(16)
    with Connection(IN_MEMORY_URI) as conn:
        with closing(conn.SimpleQueue(queue_name)) as simple_queue:
            simple_queue.put(job_str, retry=True)

    # we use construct to avoid pydantic validation as IN_MEMORY_URI is not a valid URL
    mq_conn_info = MessageQueueConnectionInfo.construct(uri=IN_MEMORY_URI, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)

    with pytest.raises(JobError) as exc_info:
        job.get_details()
    assert "Could not get job details" in str(exc_info.value)
