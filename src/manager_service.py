#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Manage the service of github-runner-manager."""

import json
import logging
import os
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
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system")
GITHUB_RUNNER_MANAGER_PACKAGE = "github_runner_manager"
GITHUB_RUNNER_MANAGER_PACKAGE_PATH = "./github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_NAME = "github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR = Path("/var/log/github-runner-manager")
GITHUB_RUNNER_MANAGER_SERVICE_EXECUTABLE_PATH = "/usr/local/bin/github-runner-manager"

_INSTALL_ERROR_MESSAGE = "Unable to install github-runner-manager package from source"
_SERVICE_SETUP_ERROR_MESSAGE = "Unable to enable or start the github-runner-manager application"
_SERVICE_STOP_ERROR_MESSAGE = "Unable to stop the github-runner-manager application"

logger = logging.getLogger(__name__)


def get_http_port_for_unit(unit_name: str) -> int:
    """Return a stable HTTP port for a unit based on its index.

    Args:
        unit_name: The Juju unit name (e.g., app/0).

    Returns:
        Port number derived from a deterministic base + unit index.
    """
    try:
        index = int(unit_name.split("/")[-1])
    except (ValueError, IndexError):
        index = 0
    return _BASE_PORT + index


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


def install_package() -> None:
    """Install the GitHub runner manager package.

    Raises:
        RunnerManagerApplicationInstallError: Unable to install the application.
    """
    _stop()

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
            ["pipx", "install", "--global", "--force", GITHUB_RUNNER_MANAGER_PACKAGE_PATH]
        )
    except SubprocessError as err:
        raise RunnerManagerApplicationInstallError(_INSTALL_ERROR_MESSAGE) from err


def stop() -> None:
    """Stop the GitHub runner manager service."""
    _stop()


def _stop() -> None:
    """Stop the GitHub runner manager service.

    Raises:
        RunnerManagerApplicationStopError: Failed to stop the service.
    """
    # Best-effort stop for this unit's instance service; if unit name is not available
    # fall back to stopping the generic service name if present.
    try:
        # Attempt to read JUJU_UNIT_NAME from environment as a fallback for stop hooks
        unit_name = os.environ.get("JUJU_UNIT_NAME", "")
        service_name = (
            _instance_service_name(unit_name) if unit_name else GITHUB_RUNNER_MANAGER_SERVICE_NAME
        )
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
    unit_dir = Path("/var/lib/github-runner-manager") / _normalized_unit(unit_name)
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
        KillMode=control-group
        TimeoutStopSec=30
        StandardOutput=append:{log_file}
        StandardError=append:{log_file}

        [Install]
        WantedBy=multi-user.target
        """
    )
    service_path = (
        SYSTEMD_SERVICE_PATH / f"{GITHUB_RUNNER_MANAGER_SERVICE_NAME}@{instance}.service"
    )
    service_path.write_text(service_file_content, "utf-8")
