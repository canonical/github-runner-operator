#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test for client to interact with github-runner-manager service."""

from unittest.mock import MagicMock

import pytest
import requests

from errors import RunnerManagerServiceConnectionError, RunnerManagerServiceResponseError
from manager_client import (
    CONNECTION_ERROR_MESSAGE,
    NO_RESPONSE_ERROR_MESSAGE,
    GitHubRunnerManagerClient,
)


@pytest.fixture(name="mock__request")
def mock_requests_fixture() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="client")
def client_fixture(mock__request: MagicMock):
    client = GitHubRunnerManagerClient("mock_ip", "mock_port")
    # Remove the request session as safe guard against issues real requests.
    client._requests = None
    client._request = mock__request
    return client


def test_check_runner_success(client: GitHubRunnerManagerClient, mock__request: MagicMock) -> None:
    """
    arrange: Setup the response for the service.
    act: Request for runner information.
    assert: The return value is correct.
    """
    mock_response = MagicMock()
    mock_response.text = (
        '{"online": 0, "busy": 0, "offline": 0, "unknown": 0, "runners": [], "busy_runners": []}'
    )
    mock__request.return_value = mock_response

    info = client.check_runner()
    # The underscore should be replaced with dash, as Juju action results cannot have underscores.
    assert info == {
        "online": 0,
        "busy": 0,
        "offline": 0,
        "unknown": 0,
        "runners": (),
        "busy-runners": (),
    }


def test_check_runner_http_error(
    client: GitHubRunnerManagerClient, mock__request: MagicMock
) -> None:
    """
    arrange: Setup the response for the service to raise HTTPError with response of 400.
    act: Request for runner information.
    assert: The error value is correct.
    """
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Mock response"
    mock__request.side_effect = requests.HTTPError("mock error", response=mock_response)

    with pytest.raises(RunnerManagerServiceResponseError) as err:
        client.check_runner()

    assert "400" in str(err.value)
    assert "Mock response" in str(err.value)


def test_check_runner_http_error_no_response(
    client: GitHubRunnerManagerClient, mock__request: MagicMock
) -> None:
    """
    arrange: Setup the response for the service to raise HTTPError without response.
    act: Request for runner information.
    assert: The error value is correct.
    """
    mock__request.side_effect = requests.HTTPError("mock error", response=None)

    with pytest.raises(RunnerManagerServiceResponseError) as err:
        client.check_runner()

    assert NO_RESPONSE_ERROR_MESSAGE in str(err.value)


def test_check_runner_connection_error(
    client: GitHubRunnerManagerClient, mock__request: MagicMock
) -> None:
    """
    arrange: Setup the response for the service to raise ConnectionError.
    act: Request for runner information.
    assert: The error value is correct.
    """
    mock__request.side_effect = requests.ConnectionError("Mock error")

    with pytest.raises(RunnerManagerServiceConnectionError) as err:
        client.check_runner()

    assert CONNECTION_ERROR_MESSAGE in str(err.value)
