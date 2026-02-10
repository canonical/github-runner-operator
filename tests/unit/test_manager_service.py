#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test for manager_service."""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class PatchedPaths:
    """Expose monkeypatched paths so tests can reference them when needed.

    Attributes:
        package_path: Path to the mocked github-runner-manager package source.
        systemd_service_path: Path to the mocked systemd service directory.
        service_log_dir: Path to the mocked log directory for the manager service.
        service_dir: Path to the mocked service state directory.
        home_path: Path serving as a temp root for per-unit files in tests.
    """

    package_path: Path
    systemd_service_path: Path
    service_log_dir: Path
    service_dir: Path
    home_path: Path


@pytest.fixture(name="patched_paths", autouse=True)
def patched_paths_fixture(monkeypatch, tmp_path) -> PatchedPaths:
    paths = PatchedPaths(
        package_path=tmp_path / "github-runner-manager",
        systemd_service_path=tmp_path / "etc" / "systemd" / "system",
        service_log_dir=tmp_path / "var" / "log" / "github-runner-manager",
        service_dir=tmp_path / "var" / "lib" / "github-runner-manager",
        home_path=tmp_path / "home",
    )

    monkeypatch.setattr(manager_service, "GITHUB_RUNNER_MANAGER_PACKAGE_PATH", paths.package_path)
    monkeypatch.setattr(manager_service, "SYSTEMD_SERVICE_PATH", paths.systemd_service_path)
    monkeypatch.setattr(
        manager_service, "GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR", paths.service_log_dir
    )
    monkeypatch.setattr(manager_service, "GITHUB_RUNNER_MANAGER_SERVICE_DIR", paths.service_dir)

    return paths


@pytest.fixture(name="mock_systemd")
def mock_systemd_fixture(monkeypatch):
    mock_systemd = MagicMock()
    monkeypatch.setattr("manager_service.systemd", mock_systemd)
    return mock_systemd


@pytest.fixture(name="mock_execute_command")
def mock_execute_command_fixture(monkeypatch):
    mock_execute_command = MagicMock(return_value=("Mock", 0))
    monkeypatch.setattr("manager_service.execute_command", mock_execute_command)
    return mock_execute_command


def test_setup_started(
    complete_charm_state: CharmState,
    patched_paths: PatchedPaths,
    mock_systemd: MagicMock,
    mock_execute_command: MagicMock,
    monkeypatch,
):
    """
    arrange: Mock the service to be running.
    act: Run the setup function.
    assert: The files are written, and the systemd is called. System service start is not called.
    """
    mock_systemd.service_running.return_value = True
    unit_name = "mock_unit"
    # Ensure manager_service writes config under the mock home path
    monkeypatch.setattr(
        manager_service, "GITHUB_RUNNER_MANAGER_SERVICE_DIR", patched_paths.home_path
    )
    manager_service.setup(complete_charm_state, "mock_app", unit_name)

    service_path = (
        patched_paths.systemd_service_path / f"github-runner-manager@{unit_name}.service"
    )
    service_content = service_path.read_text()
    assert "User=runner-manager" in service_content
    assert "Group=runner-manager" in service_content
    config_path = patched_paths.home_path / unit_name / "config.yaml"
    assert (
        f"ExecStart=github-runner-manager --config-file {config_path} --host 127.0.0.1 --port 55555"
        in service_content
    )
    assert "Restart=on-failure" in service_content

    config_content = (patched_paths.home_path / unit_name / "config.yaml").read_text()
    # Check some configuration options
    assert "openstack_configuration:" in config_content
    assert "manager_proxy_command: ssh -W %h:%p example.com" in config_content
    assert "non_reactive_configuration:" in config_content
    assert "mongodb_uri: mongodb://user:password@localhost:27017" in config_content

    mock_systemd.service_enable.assert_called_once()
    mock_systemd.service_start.assert_not_called()


def test_setup_no_started(
    complete_charm_state: CharmState,
    mock_systemd: MagicMock,
    mock_execute_command: MagicMock,
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
    complete_charm_state: CharmState,
    mock_systemd: MagicMock,
    mock_execute_command: MagicMock,
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
        manager_service.install_package(unit_name="test-unit/1")

    assert manager_service._INSTALL_ERROR_MESSAGE in str(err.value)


def test_stop_with_running_service(mock_systemd: MagicMock):
    """
    arrange: The service is running.
    act: Run stop.
    assert: There is a call for stopping service.
    """
    mock_systemd.service_running.return_value = True
    manager_service.stop(unit_name="test-unit/0")
    mock_systemd.service_running.assert_called_once()
    mock_systemd.service_stop.assert_called_once()


def test_stop_with_stopped_service(mock_systemd: MagicMock):
    """
    arrange: The service is stopped.
    act: Run stop.
    assert: There is no call for stopping service.
    """
    mock_systemd.service_running.return_value = False
    manager_service.stop(unit_name="test-unit/0")
    mock_systemd.service_running.assert_called_once()
    mock_systemd.service_stop.assert_not_called()


# 2026-01-19 Skip the mocks fixture to test the actual ensure_http_port_for_unit implementation.
# The mocks fixture (see conftest.py) normally patches this function to return 55555.
@pytest.mark.nomocks
def test_get_http_port_persists_and_reuses(tmp_path, monkeypatch):
    """
    Arrange: isolate filesystem via Path monkeypatch and stub ports as available.
    Act: request a port twice for the same unit, flipping availability between calls.
    Assert: first call writes and returns a port; second call reuses persisted value.
    """
    # Scenario 1: port is available, should be allocated and persisted.
    monkeypatch.setattr(manager_service, "_port_available", lambda host, port: True)
    unit_name = "github-runner-operator/0"

    first_port = manager_service.ensure_http_port_for_unit(unit_name)

    unit_dir = tmp_path / "var/lib/github-runner-manager" / unit_name.replace("/", "-")
    port_file = unit_dir / "http_port"
    assert port_file.exists(), "Expected persisted port file"
    assert int(port_file.read_text(encoding="utf-8").strip()) == first_port

    # Scenario 2: port is not available, but persisted value should be reused.
    monkeypatch.setattr(manager_service, "_port_available", lambda host, port: False)

    second_port = manager_service.ensure_http_port_for_unit(unit_name)

    assert second_port == first_port, "Expected persisted port to be reused"


# 2026-01-19 Skip the mocks fixture to test the actual ensure_http_port_for_unit implementation.
# The mocks fixture (see conftest.py) normally patches this function to return 55555.
@pytest.mark.nomocks
def test_get_http_port_collision_scan(tmp_path, monkeypatch):
    """
    Arrange: map Path to temp root and stub availability so base and next two are busy.
    Act: request a port for a unit whose base is 55555.
    Assert: selected port is base+3 and persisted to the per-unit file.
    """

    def stub_port_available(host, port):
        """Simulate port availability.

        Args:
            host: Host address (ignored in this stub).
            port: Port number to evaluate.

        Returns:
            True when ``port`` is greater than or equal to ``base+3``; otherwise False.

        Notes:
            Base port 55555 and the next two ports are busy; ports from base+3 onward
            are available.
        """
        base_port = manager_service._BASE_PORT
        return port >= base_port + 3

    monkeypatch.setattr(manager_service, "_port_available", stub_port_available)
    unit_name = "github-runner-operator/0"

    selected_port = manager_service.ensure_http_port_for_unit(unit_name)

    assert selected_port == manager_service._BASE_PORT + 3
    unit_dir = tmp_path / "var/lib/github-runner-manager" / unit_name.replace("/", "-")
    port_file = unit_dir / "http_port"
    assert int(port_file.read_text(encoding="utf-8").strip()) == selected_port


@pytest.mark.parametrize(
    "persisted_offsets, expected_offset",
    [
        ([0], 1),
        ([0, 1, 2], 3),
    ],
)
# 2026-01-19 Skip the mocks fixture to test the actual ensure_http_port_for_unit implementation.
# The mocks fixture (see conftest.py) normally patches this function to return 55555.
@pytest.mark.nomocks
def test_select_http_port_skips_persisted_ports(
    patched_paths: PatchedPaths, monkeypatch, persisted_offsets, expected_offset
):
    """
    arrange: Persist candidate ports for other units and stub availability to True.
    act: Request a port for unit "app/0" whose base may collide with persisted ones.
    assert: Selected port equals base+expected_offset and is persisted for this unit.
    """
    monkeypatch.setattr(manager_service, "_port_available", lambda host, port: True)

    base = manager_service._BASE_PORT
    # Persist the candidate ports under different unit directories to simulate other units.
    for idx, off in enumerate(persisted_offsets):
        unit_dir = patched_paths.service_dir / f"other-{idx}"
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "http_port").write_text(str(base + off), encoding="utf-8")

    selected = manager_service.ensure_http_port_for_unit("app/0")

    assert selected == base + expected_offset
    this_unit_dir = patched_paths.service_dir / "app-0"
    assert int((this_unit_dir / "http_port").read_text(encoding="utf-8").strip()) == selected
