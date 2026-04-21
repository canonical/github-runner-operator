#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for HTTP server."""

import json
from multiprocessing import Process
from threading import Lock
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from github_runner_manager.http_server import RUNNER_MANAGER_CONFIG_NAME, app
from github_runner_manager.manager.runner_manager import FlushMode, RunnerInfo


@pytest.fixture(name="lock", scope="function")
def lock_fixture() -> Lock:
    return Lock()


@pytest.fixture(name="mock_runner_manager", scope="function")
def mock_runner_manager_fixture() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="client", scope="function")
def client_fixture(
    lock: Lock, mock_runner_manager: MagicMock, monkeypatch
) -> Iterator[FlaskClient]:
    app.debug = True
    app.config["TESTING"] = True
    app.config[RUNNER_MANAGER_CONFIG_NAME] = mock_runner_manager

    monkeypatch.setattr("github_runner_manager.http_server._lock", lock)
    with app.test_client() as client:
        yield client


def test_flush_runner_default_args(
    client: FlaskClient, lock: Lock, mock_runner_manager: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with a mock runner manager.
    act: Run flush runner with no args.
    assert: Should flush idle runners.
    """
    response = client.post("/runner/flush")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_manager.flush_runners.assert_called_once_with(FlushMode.FLUSH_IDLE)


def test_flush_runner_flush_busy(
    client: FlaskClient, lock: Lock, mock_runner_manager: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with a mock runner manager.
    act: Run flush runner with flush-busy = True.
    assert: Should flush both idle and busy runners.
    """
    response = client.post("/runner/flush?flush-busy=true")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_manager.flush_runners.assert_called_once_with(FlushMode.FLUSH_BUSY)


def test_flush_runner_unlocked(
    client: FlaskClient, lock: Lock, mock_runner_manager: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with a mock runner manager. The lock is unlocked.
    act: Run flush runner.
    assert: The flush runner should run.
    """
    response = client.post("/runner/flush?flush-busy=false")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_manager.flush_runners.assert_called_once_with(FlushMode.FLUSH_IDLE)


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


def test_check_runner(client: FlaskClient, lock: Lock, mock_runner_manager: MagicMock) -> None:
    """
    arrange: Mock runner manager to return a RunnerInfo.
    act: HTTP Get to /runner/check.
    assert: Returns the correct status code and serialized RunnerInfo.
    """
    mock_runner_manager.get_runner_info.return_value = RunnerInfo(
        online=2,
        busy=1,
        offline=1,
        unknown=1,
        runners=("idle-runner", "busy-runner"),
        busy_runners=("busy-runner",),
    )

    response = client.get("/runner/check")

    assert response.status_code == 200
    assert not lock.locked()
    data = json.loads(response.text)
    assert data == {
        "online": 2,
        "busy": 1,
        "offline": 1,
        "unknown": 1,
        "runners": ["idle-runner", "busy-runner"],
        "busy_runners": ["busy-runner"],
    }
