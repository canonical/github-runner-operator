#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for HTTP server."""

import json
from multiprocessing import Process
from threading import Lock
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from github_runner_manager.manager.runner_manager import FlushMode
from src.github_runner_manager.http_server import APP_CONFIG_NAME, OPENSTACK_CONFIG_NAME, app
from src.github_runner_manager.manager.runner_scaler import RunnerInfo, RunnerScaler


@pytest.fixture(name="lock", scope="function")
def lock_fixture() -> Lock:
    return Lock()


@pytest.fixture(name="client", scope="function")
def client_fixture(lock: Lock, monkeypatch) -> Iterator[FlaskClient]:
    app.debug = True
    app.config["TESTING"] = True
    app.config[APP_CONFIG_NAME] = MagicMock()
    app.config[OPENSTACK_CONFIG_NAME] = MagicMock()

    monkeypatch.setattr("src.github_runner_manager.http_server._lock", lock)
    with app.test_client() as client:
        yield client


@pytest.fixture(name="mock_runner_scaler", scope="function")
def mock_runner_scaler_fixture(monkeypatch) -> MagicMock:
    mock = MagicMock(spec=RunnerScaler)
    monkeypatch.setattr(
        "src.github_runner_manager.http_server.RunnerScaler.build", lambda x, z: mock
    )
    return mock


def test_flush_runner_default_args(
    client: FlaskClient, lock: Lock, mock_runner_scaler: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with client.
    act: Run flush runner with no args.
    assert: Should flush idle runners.
    """
    app.config["lock"] = lock

    response = client.post("/runner/flush")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_scaler.flush.assert_called_once_with(FlushMode.FLUSH_IDLE)


def test_flush_runner_flush_busy(
    client: FlaskClient, lock: Lock, mock_runner_scaler: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with client.
    act: Run flush runner with flush-busy = True.
    assert: Should flush both idle and busy runners.

    """
    app.config["lock"] = lock

    response = client.post("/runner/flush?flush-busy=true")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_scaler.flush.assert_called_once_with(FlushMode.FLUSH_BUSY)


def test_flush_runner_unlocked(
    client: FlaskClient, lock: Lock, mock_runner_scaler: MagicMock
) -> None:
    """
    arrange: Start up a test flask server with client. The lock is unlocked.
    act: Run flush runner.
    assert: The flush runner should run.
    """
    app.config["lock"] = lock

    response = client.post("/runner/flush?flush-busy=false")

    assert response.status_code == 204
    assert not lock.locked()
    mock_runner_scaler.flush.assert_called_once_with(FlushMode.FLUSH_IDLE)


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


def test_check_runner(client: FlaskClient, lock: Lock, mock_runner_scaler: MagicMock) -> None:
    """
    arrange: Mock runner scaler to return mock data on get runner info.
    act: HTTP Get to /runner/check
    assert: Returns the correct status code and content.
    """
    app.config["lock"] = lock
    mock_runner_scaler.get_runner_info.return_value = RunnerInfo(
        online=1, busy=0, offline=0, unknown=0, runners=("mock_runner",), busy_runners=tuple()
    )

    response = client.get("/runner/check")

    assert response.status_code == 200
    assert not lock.locked()
    assert json.loads(response.text) == {
        "online": 1,
        "busy": 0,
        "offline": 0,
        "unknown": 0,
        "runners": ["mock_runner"],
        "busy_runners": [],
    }
