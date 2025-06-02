#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Manage the service of github-runner-manager."""

import json
import logging
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
    SubprocessError,
)
from factories import create_application_configuration
from utilities import execute_command

GITHUB_RUNNER_MANAGER_ADDRESS = "127.0.0.1"
GITHUB_RUNNER_MANAGER_PORT = "55555"
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system")
GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE = "github-runner-manager.service"
GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH = (
    SYSTEMD_SERVICE_PATH / GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE
)
GITHUB_RUNNER_MANAGER_PACKAGE = "github_runner_manager"
JOB_MANAGER_PACKAGE = "jobmanager_client"
GITHUB_RUNNER_MANAGER_PACKAGE_PATH = "./github-runner-manager"
JOB_MANAGER_PACKAGE_PATH = "./jobmanager/client"
GITHUB_RUNNER_MANAGER_SERVICE_NAME = "github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR = Path("/var/log/github-runner-manager")

_INSTALL_ERROR_MESSAGE = "Unable to install github-runner-manager package from source"
_SERVICE_SETUP_ERROR_MESSAGE = "Unable to enable or start the github-runner-manager application"
_SERVICE_STOP_ERROR_MESSAGE = "Unable to stop the github-runner-manager application"

logger = logging.getLogger(__name__)


def setup(state: CharmState, app_name: str, unit_name: str) -> None:
    """Set up the github-runner-manager service.

    Args:
        state: The state of the charm.
        app_name: The Juju application name.
        unit_name: The Juju unit.

    Raises:
        RunnerManagerApplicationStartError: Setup of the runner manager service has failed.
    """
    try:
        if systemd.service_running(GITHUB_RUNNER_MANAGER_SERVICE_NAME):
            systemd.service_stop(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err
    config = create_application_configuration(state, app_name, unit_name)
    config_file = _setup_config_file(config)
    GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = _get_log_file_path(unit_name)
    log_file_path.touch(exist_ok=True)
    _setup_service_file(config_file, log_file_path)
    _enable_service()


def install_package() -> None:
    """Install the GitHub runner manager package.

    Raises:
        RunnerManagerApplicationInstallError: Unable to install the application.
    """
    try:
        if systemd.service_running(GITHUB_RUNNER_MANAGER_SERVICE_NAME):
            systemd.service_stop(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
    except SystemdError as err:
        raise RunnerManagerApplicationInstallError(_SERVICE_STOP_ERROR_MESSAGE) from err

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
        execute_command(
            [
                "pipx",
                "inject",
                "--global",
                "--force",
                GITHUB_RUNNER_MANAGER_PACKAGE,
                JOB_MANAGER_PACKAGE_PATH,
            ]
        )
    except SubprocessError as err:
        raise RunnerManagerApplicationInstallError(_INSTALL_ERROR_MESSAGE) from err


def _get_log_file_path(unit_name: str) -> Path:
    """Get the log file path.

    Args:
        unit_name: The Juju unit name.

    Returns:
        The path to the log file.
    """
    log_name = unit_name.replace("/", "-") + ".log"
    return GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR / log_name


def _enable_service() -> None:
    """Enable the github runner manager service.

    Raises:
        RunnerManagerApplicationStartError: Unable to startup the service.
    """
    try:
        systemd.service_enable(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
        if not systemd.service_running(GITHUB_RUNNER_MANAGER_SERVICE_NAME):
            systemd.service_start(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err


def _setup_config_file(config: ApplicationConfiguration) -> Path:
    """Write the configuration to file.

    Args:
        config: The application configuration.
    """
    # Directly converting to `dict` will have the value be Python objects rather than string
    # representations. The values needs to be string representations to be converted to YAML file.
    # No easy way to directly convert to YAML file, so json module is used.
    config_dict = json.loads(config.json())
    path = Path(f"~{constants.RUNNER_MANAGER_USER}").expanduser() / "config.yaml"
    with open(path, "w+", encoding="utf-8") as file:
        yaml_safe_dump(config_dict, file)
    return path


def _setup_service_file(config_file: Path, log_file: Path) -> None:
    """Configure the systemd service.

    Args:
        config_file: The configuration file for the service.
        log_file: The file location to store the logs.
    """
    service_file_content = textwrap.dedent(
        f"""\
        [Unit]
        Description=Runs the github-runner-manager service

        [Service]
        Type=simple
        User={constants.RUNNER_MANAGER_USER}
        Group={constants.RUNNER_MANAGER_GROUP}
        ExecStart=github-runner-manager --config-file {str(config_file)} --host \
{GITHUB_RUNNER_MANAGER_ADDRESS} --port {GITHUB_RUNNER_MANAGER_PORT}
        Restart=on-failure
        StandardOutput=append:{log_file}
        StandardError=append:{log_file}

        [Install]
        WantedBy=multi-user.target
        """
    )
    GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH.write_text(service_file_content, "utf-8")
