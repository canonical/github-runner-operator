#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for HTTP server."""

import logging
from multiprocessing import Process
from threading import Lock
from typing import Iterator

import pytest
from flask.testing import FlaskClient

from src.github_runner_manager.http_server import app


@pytest.fixture(name="lock", scope="function")
def lock_fixture() -> Lock:
    return Lock()


@pytest.fixture(name="client", scope="function")
def client_fixture(lock: Lock) -> Iterator[FlaskClient]:
    app.debug = True
    app.config["TESTING"] = True

    app.config["lock"] = lock
    with app.test_client() as client:
        yield client


def test_flush_runner_default_args(client: FlaskClient, lock: Lock, caplog) -> None:
    """
    arrange: Start up a test flask server with client.
    act: Run flush runner with no args.
    assert: Should flush idle runners.
    """
    with caplog.at_level(logging.INFO):
        app.config["lock"] = lock
        client = app.test_client()

        response = client.post("/runner/flush")

    log_lines = [record.message for record in caplog.records]

    assert response.status_code == 200
    assert not lock.locked()
    assert "Flushing idle runners..." in log_lines
    assert "Flushed the runners" in log_lines


def test_flush_runner_flush_busy(client: FlaskClient, lock: Lock, caplog) -> None:
    """
    arrange: Start up a test flask server with client.
    act: Run flush runner with flush-busy = True.
    assert: Should flush both idle and busy runners.

    """
    with caplog.at_level(logging.INFO):
        app.config["lock"] = lock
        client = app.test_client()

        response = client.post("/runner/flush", headers={"flush-runner": "true"})

    log_lines = [record.message for record in caplog.records]

    assert response.status_code == 200
    assert not lock.locked()
    assert "Flushing idle runners..." in log_lines
    assert "Flushed the runners" in log_lines


def test_flush_runner_unlocked(client: FlaskClient, lock: Lock, caplog) -> None:
    """
    arrange: Start up a test flask server with client. The lock is unlocked.
    act: Run flush runner.
    assert: The flush runner should run.
    """
    with caplog.at_level(logging.INFO):
        app.config["lock"] = lock
        client = app.test_client()

        response = client.post("/runner/flush", headers={"flush-runner": "false"})

    log_lines = [record.message for record in caplog.records]

    assert response.status_code == 200
    assert not lock.locked()
    assert "Flushed the runners" in log_lines


def test_flush_runner_locked(client: FlaskClient, lock: Lock) -> None:
    """
    arrange: Start up a test flask server with client. The lock is locked.
    act: Run flush runner.
    assert: The flush runner call should wait on the lock indefinitely.
    """
    lock.acquire()

    # Due to FlaskClient.post not supporting timeout, Process is used to control the termination.
    # Using Process means the caplog is unable to capture the logs.
    flush = Process(target=client.post, args=("/runner/flush",))
    flush.start()
    assert flush.is_alive(), "The flush runner call should still be waiting on the lock"

    flush.terminate()
