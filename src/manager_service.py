#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Manage the service of github-runner-manager."""
import fcntl
import json
import logging
import os
import socket
import textwrap
from pathlib import Path

from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v1.systemd import SystemdError
from github_runner_manager import constants
from github_runner_manager.configuration.base import ApplicationConfiguration
from yaml import safe_dump as yaml_safe_dump

from charm_state import CharmState
from errors import (
    RunnerManagerApplicationInstallError,
    RunnerManagerApplicationStartError,
    RunnerManagerApplicationStopError,
    SubprocessError,
)
from factories import create_application_configuration
from utilities import execute_command

GITHUB_RUNNER_MANAGER_ADDRESS = "127.0.0.1"
_BASE_PORT = 55555
_PORT_SCAN_SPAN = 100  # how many ports to try beyond base if occupied
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system")
GITHUB_RUNNER_MANAGER_PACKAGE = "github_runner_manager"
GITHUB_RUNNER_MANAGER_PACKAGE_PATH = Path("./github-runner-manager")
GITHUB_RUNNER_MANAGER_SERVICE_NAME = "github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR = Path("/var/log/github-runner-manager")
GITHUB_RUNNER_MANAGER_SERVICE_DIR = Path("/var/lib/github-runner-manager")

_INSTALL_ERROR_MESSAGE = "Unable to install github-runner-manager package from source"
_SERVICE_SETUP_ERROR_MESSAGE = "Unable to enable or start the github-runner-manager application"
_SERVICE_STOP_ERROR_MESSAGE = "Unable to stop the github-runner-manager application"

logger = logging.getLogger(__name__)


def get_http_port_for_unit(unit_name: str) -> int:
    """Return the per-unit HTTP port, allocating if needed.

    This will first try to read a persisted port for the unit. If none exists,
    it will pick a deterministic candidate based on the unit index, and probe
    availability, scanning a small bounded range on collisions. The selection
    is persisted to avoid future changes.

    Port allocation lock is used to avoid multiple units probing ports
    simultaneously.

    Args:
        unit_name: The Juju unit name (e.g., app/0).

    Returns:
        The selected/persisted HTTP port for the unit.
    """
    unit_dir = GITHUB_RUNNER_MANAGER_SERVICE_DIR / _normalized_unit(unit_name)
    unit_dir.mkdir(parents=True, exist_ok=True)
    port_file = unit_dir / "http_port"
    if port_file.exists():
        try:
            return int(port_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pass

    port_allocation_lock = GITHUB_RUNNER_MANAGER_SERVICE_DIR / "port-alloc.lock"
    port_allocation_lock.parent.mkdir(parents=True, exist_ok=True)
    with port_allocation_lock.open("w+", encoding="utf-8") as lock_f:
        try:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            selected = _select_http_port(unit_name)
            port_file.write_text(str(selected), encoding="utf-8")
            return selected
        finally:
            try:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _select_http_port(unit_name: str) -> int:
    """Choose an available HTTP port for the unit.

    Prefers the deterministic candidate derived from unit index; on collision,
    scan a small bounded range on 127.0.0.1.

    Return the base port if all busy; systemd start will fail and surface error.
    """
    base = _deterministic_port_for_unit(unit_name)
    if _port_available(GITHUB_RUNNER_MANAGER_ADDRESS, base):
        return base
    for offset in range(1, _PORT_SCAN_SPAN + 1):
        cand = base + offset
        if _port_available(GITHUB_RUNNER_MANAGER_ADDRESS, cand):
            return cand
    return base


def _deterministic_port_for_unit(unit_name: str) -> int:
    """Derive a deterministic base port from the unit index.

    Args:
        unit_name: The Juju unit name (e.g., app/0).

    Returns:
        Base port number calculated as `_BASE_PORT + unit_index`.
    """
    try:
        index = int(unit_name.split("/")[-1])
    except (ValueError, IndexError):
        index = 0
    return _BASE_PORT + index


def _port_available(host: str, port: int) -> bool:
    """Check if a TCP port is available for binding on the given host.

    Args:
        host: Host address to bind to.
        port: Port number to check.

    Returns:
        True if binding succeeds (port available), otherwise False.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def _normalized_unit(unit_name: str) -> str:
    """Normalize a Juju unit name to a safe identifier.

    Args:
        unit_name: The Juju unit name (e.g., app/0).

    Returns:
        Normalized name (e.g., app-0).
    """
    return unit_name.replace("/", "-")


def _instance_service_name(unit_name: str) -> str:
    """Build the systemd instance service name for a unit."""
    return f"{GITHUB_RUNNER_MANAGER_SERVICE_NAME}@{_normalized_unit(unit_name)}"


def setup(state: CharmState, app_name: str, unit_name: str) -> None:
    """Set up the github-runner-manager service.

    Args:
        state: The state of the charm.
        app_name: The Juju application name.
        unit_name: The Juju unit.

    Raises:
        RunnerManagerApplicationStartError: Setup of the runner manager service has failed.
    """
    instance_service = _instance_service_name(unit_name)
    try:
        if systemd.service_running(instance_service):
            systemd.service_stop(instance_service)
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err

    config = create_application_configuration(state, app_name, unit_name)
    config_file = _setup_config_file(config, unit_name)
    GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = _get_log_file_path(unit_name)
    log_file_path.touch(exist_ok=True)
    _setup_service_file(
        unit_name,
        config_file,
        log_file_path,
        state.charm_config.runner_manager_log_level,
    )
    try:
        systemd.daemon_reload()
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err
    _enable_service(unit_name)


def install_package(unit_name: str) -> None:
    """Install the GitHub runner manager package.

    Args:
        unit_name: The Juju unit name.

    Raises:
        RunnerManagerApplicationInstallError: Unable to install the application.
    """
    _stop(unit_name)

    logger.info("Ensure pipx is at latest version")
    try:
        execute_command(
            ["pip", "install", "--prefix", "/usr", "--ignore-installed", "--upgrade", "pipx"]
        )
    except SubprocessError as err:
        raise RunnerManagerApplicationInstallError(_INSTALL_ERROR_MESSAGE) from err

    logger.info("Installing github-runner-manager package as executable")
    try:
        # pipx with `--force` will always overwrite the current installation.
        execute_command(
            [
                "pipx",
                "install",
                "--global",
                "--force",
                str(GITHUB_RUNNER_MANAGER_PACKAGE_PATH.absolute()),
            ]
        )
    except SubprocessError as err:
        raise RunnerManagerApplicationInstallError(_INSTALL_ERROR_MESSAGE) from err


def stop(unit_name: str) -> None:
    """Stop the GitHub runner manager service.

    Args:
        unit_name: The Juju unit name.
    """
    _stop(unit_name)


def _stop(unit_name: str) -> None:
    """Stop the GitHub runner manager service.

    Args:
        unit_name: The Juju unit name.

    Raises:
        RunnerManagerApplicationStopError: Failed to stop the service.
    """
    try:
        service_name = _instance_service_name(unit_name)
        if systemd.service_running(service_name):
            systemd.service_stop(service_name)
    except SystemdError as err:
        raise RunnerManagerApplicationStopError(_SERVICE_STOP_ERROR_MESSAGE) from err


def _get_log_file_path(unit_name: str) -> Path:
    """Get the log file path.

    Args:
        unit_name: The Juju unit name.

    Returns:
        The path to the log file.
    """
    log_name = unit_name.replace("/", "-") + ".log"
    return GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR / log_name


def _enable_service(unit_name: str) -> None:
    """Enable the github runner manager service.

    Raises:
        RunnerManagerApplicationStartError: Unable to startup the service.
    """
    instance_service = _instance_service_name(unit_name)
    try:
        systemd.service_enable(instance_service)
        if not systemd.service_running(instance_service):
            systemd.service_start(instance_service)
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err


def _setup_config_file(config: ApplicationConfiguration, unit_name: str) -> Path:
    """Write the configuration to a per-unit file.

    Args:
        config: The application configuration.
        unit_name: The Juju unit name used to choose the per-unit directory.
    """
    # Directly converting to `dict` will have the value be Python objects rather than string
    # representations. The values needs to be string representations to be converted to YAML file.
    # No easy way to directly convert to YAML file, so json module is used.
    config_dict = json.loads(config.json())
    unit_dir = GITHUB_RUNNER_MANAGER_SERVICE_DIR / _normalized_unit(unit_name)
    unit_dir.mkdir(parents=True, exist_ok=True)
    path = unit_dir / "config.yaml"
    with open(path, "w+", encoding="utf-8") as file:
        yaml_safe_dump(config_dict, file)
    return path


def _setup_service_file(unit_name: str, config_file: Path, log_file: Path, log_level: str) -> None:
    """Configure the per-unit systemd service.

    Args:
        unit_name: The Juju unit name used to render the instance service.
        config_file: The configuration file for the service.
        log_file: The file location to store the logs.
        log_level: The log level of the service.
    """
    python_path = Path(os.getcwd()) / "venv"
    instance = _normalized_unit(unit_name)
    http_port = get_http_port_for_unit(unit_name)
    service_file_content = textwrap.dedent(
        f"""\
        [Unit]
        Description=Runs the github-runner-manager service
        StartLimitIntervalSec=0

        [Service]
        Type=simple
        User={constants.RUNNER_MANAGER_USER}
        Group={constants.RUNNER_MANAGER_GROUP}
        ExecStart=github-runner-manager --config-file {str(config_file)} --host \
{GITHUB_RUNNER_MANAGER_ADDRESS} --port {http_port} \
--python-path {str(python_path)} --log-level {log_level}
        Restart=on-failure
        RestartSec=30
        RestartSteps=5
        RestartMaxDelaySec=600
        KillMode=process
        StandardOutput=append:{log_file}
        StandardError=append:{log_file}

        [Install]
        WantedBy=multi-user.target
        """
    )
    service_path = (
        SYSTEMD_SERVICE_PATH / f"{GITHUB_RUNNER_MANAGER_SERVICE_NAME}@{instance}.service"
    )
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service_file_content, "utf-8")
