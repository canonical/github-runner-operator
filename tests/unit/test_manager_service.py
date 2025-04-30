#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test for manager_service."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import manager_service
from charm_state import CharmState
from errors import (
    RunnerManagerApplicationInstallError,
    RunnerManagerApplicationStartError,
    SubprocessError,
)
from manager_service import SystemdError


@pytest.fixture(name="mock_service_path")
def mock_service_path_fixture(tmp_path_factory):
    return tmp_path_factory.mktemp("service") / "mock.service"


@pytest.fixture(name="mock_home_path")
def mock_home_path_fixture(tmp_path_factory):
    return tmp_path_factory.mktemp("home")


@pytest.fixture(name="mock_systemd")
def mock_systemd_fixture(monkeypatch):
    mock_systemd = MagicMock()
    monkeypatch.setattr("manager_service.systemd", mock_systemd)
    return mock_systemd


@pytest.fixture(name="mock_execute_command")
def mock_execute_command_fixture(monkeypatch):
    mock_execute_command = MagicMock()
    monkeypatch.setattr("manager_service.execute_command", mock_execute_command)
    return mock_execute_command


@pytest.fixture(name="patch_file_paths")
def patch_file_paths(monkeypatch, mock_service_path, mock_home_path):
    """Patch the file path used."""
    monkeypatch.setattr(
        "manager_service.GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH", mock_service_path
    )
    monkeypatch.setattr("manager_service.Path.expanduser", lambda x: mock_home_path)


def test_setup_started(
    patch_file_paths: None,
    complete_charm_state: CharmState,
    mock_service_path: Path,
    mock_home_path: Path,
    mock_systemd: MagicMock,
):
    """
    arrange: Mock the service to be running.
    act: Run the setup function.
    assert: The files are written, and the systemd is called. System service start is not called.
    """
    mock_systemd.service_running.return_value = True
    manager_service.setup(complete_charm_state, "mock_app", "mock_unit")

    service_content = mock_service_path.read_text()
    assert "User=runner-manager" in service_content
    assert "Group=runner-manager" in service_content
    assert (
        f"ExecStart=github-runner-manager --config-file {mock_home_path}/config.yaml --host 127.0.0.1 --port 55555"
        in service_content
    )
    assert "Restart=on-failure" in service_content

    config_content = (mock_home_path / "config.yaml").read_text()
    # Check some configuration options
    assert "openstack_configuration:" in config_content
    assert "manager_proxy_command: ssh -W %h:%p example.com" in config_content
    assert "non_reactive_configuration:" in config_content
    assert "mongodb_uri: mongodb://user:password@localhost:27017" in config_content

    mock_systemd.service_enable.assert_called_once()
    mock_systemd.service_start.assert_not_called()


def test_setup_no_started(
    patch_file_paths: None, complete_charm_state: CharmState, mock_systemd: MagicMock
):
    """
    arrange: Mock the service to be not running.
    act: Run the setup function.
    assert: System service start is called.
    """
    mock_systemd.service_running.return_value = False
    manager_service.setup(complete_charm_state, "mock_app", "mock_unit")

    mock_systemd.service_enable.assert_called_once()
    mock_systemd.service_start.assert_called_once()


def test_setup_systemd_error(
    patch_file_paths: None, complete_charm_state: CharmState, mock_systemd: MagicMock
):
    """
    arrange: Mock the systemd to raise error.
    act: Run the setup function.
    assert: The correct error is re-raised.
    """
    mock_systemd.service_enable.side_effect = SystemdError("Mock error")

    with pytest.raises(RunnerManagerApplicationStartError) as err:
        manager_service.setup(complete_charm_state, "mock_app", "mock_unit")

    assert manager_service._SERVICE_SETUP_ERROR_MESSAGE in str(err.value)


def test_install_package_failure(mock_execute_command: MagicMock):
    """
    arrange: Mock execute command to raise error.
    act: Run install_package.
    assert: Correct error is raised.
    """
    mock_execute_command.side_effect = SubprocessError(
        "Mock command", 1, "mock error", "mock error"
    )

    with pytest.raises(RunnerManagerApplicationInstallError) as err:
        manager_service.install_package()

    assert manager_service._INSTALL_ERROR_MESSAGE in str(err.value)
