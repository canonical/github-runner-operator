#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the runner module."""
import secrets
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from reactive.job import Job, JobDetails, JobError, MessageQueueConnectionInfo
from reactive.runner import spawn_reactive_runner


@pytest.fixture(name="job_mock")
def job_mock_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> MagicMock:
    """Mock the job class."""
    job_mock = MagicMock(spec=Job)
    job_mock.get_details = MagicMock()
    job_mock.get_details.return_value = JobDetails(labels=["test"], run_url="http://example.com")
    job_mock.from_message_queue = MagicMock(return_value=job_mock)
    monkeypatch.setattr("reactive.runner.Job", job_mock)

    return job_mock


def test_reactive_runner(job_mock: MagicMock, caplog: LogCaptureFixture):
    """
    arrange: A runner is spawned.
    act: Call reactive_runner.
    assert: The job is received and logged.
    """
    queue_name = secrets.token_hex(16)
    spawn_reactive_runner("http://example.com", queue_name)

    job_mock.from_message_queue.assert_called_with(
        MessageQueueConnectionInfo(uri="http://example.com", queue_name=queue_name)
    )
    job_mock.get_details.assert_called_once()

    assert "Received job with labels ['test'] and run_url http://example.com" in caplog.text
    job_mock.picked_up.assert_called_once()


def test_reactive_runner_job_is_rejected_on_error(job_mock: MagicMock, caplog: LogCaptureFixture):
    """
    arrange: A runner is spawned.
    act: Call reactive_runner and raise an exception.
    assert: The job is rejected and no job details are logged.
    """
    job_mock.get_details.side_effect = JobError("test error")

    spawn_reactive_runner("http://example.com", "test-queue")

    job_mock.reject.assert_called_once()
    assert "Received job with labels ['test'] and run_url http://example.com" not in caplog.text
