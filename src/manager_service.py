#  Copyright 2025 Canonical Ltd.
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
GITHUB_RUNNER_MANAGER_PORT = "55555"
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system")
GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE = "github-runner-manager.service"
GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH = (
    SYSTEMD_SERVICE_PATH / GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE
)
GITHUB_RUNNER_MANAGER_PACKAGE = "github_runner_manager"
GITHUB_RUNNER_MANAGER_PACKAGE_PATH = "./github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_NAME = "github-runner-manager"
GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR = Path("/var/log/github-runner-manager")
GITHUB_RUNNER_MANAGER_SERVICE_EXECUTABLE_PATH = "/usr/local/bin/github-runner-manager"

# Symlink targets for logs scraped by grafana-agent and logrotate
REACTIVE_RUNNER_LOG_SYMLINK = Path("/var/log/reactive_runner")
METRICS_LOG_SYMLINK = Path("/var/log/github-runner-metrics.log")

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
    # Currently, there is some multiprocess issues that cause leftover processes.
    # This is a temp patch to clean them up.
    output, code = execute_command(
        ["/usr/bin/pkill", "-f", GITHUB_RUNNER_MANAGER_SERVICE_EXECUTABLE_PATH], check_exit=False
    )
    if code == 1:
        logger.info("No leftover github-runner-manager process to clean up.")
    elif code == 0:
        logger.warning("Clean up leftover processes.")
    else:
        logger.warning(
            "Unexpected return code %s of pkill for cleanup processes: %s", code, output
        )

    config = create_application_configuration(state, app_name, unit_name)
    config_file = _setup_config_file(config)
    GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = _get_log_file_path(unit_name)
    log_file_path.touch(exist_ok=True)
    _setup_service_file(config_file, log_file_path, state.charm_config.runner_manager_log_level)
    try:
        systemd.daemon_reload()
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err
    _enable_service()


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
    try:
        if systemd.service_running(GITHUB_RUNNER_MANAGER_SERVICE_NAME):
            systemd.service_stop(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
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
    # Ensure the config file is owned by the runner-manager user
    try:
        execute_command(
            [
                "/usr/bin/chown",
                f"{constants.RUNNER_MANAGER_USER}:{constants.RUNNER_MANAGER_GROUP}",
                str(path),
            ]
        )
    except SubprocessError:
        logger.warning("Failed to chown config.yaml to runner-manager", exc_info=True)
    return path


def _setup_service_file(config_file: Path, log_file: Path, log_level: str) -> None:
    """Configure the systemd service.

    Args:
        config_file: The configuration file for the service.
        log_file: The file location to store the logs.
        log_level: The log level of the service.
    """
    python_path = Path(os.getcwd()) / "venv"
    # Set up base directory for the runner-manager user
    # This will contain subdirectories: state/, logs/reactive/, logs/metrics/
    home_dir = Path(f"~{constants.RUNNER_MANAGER_USER}").expanduser()
    local_dir = home_dir / ".local"
    base_dir = local_dir / "state" / "github-runner-manager"

    # Create symlinks in /var/log for grafana-agent to scrape logs
    # This ensures grafana-agent can access logs from the standard /var/log location
    # Symlinks are readable by grafana-agent as confirmed by logrotate configuration
    # which uses the same paths (see src/logrotate.py)

    # Reactive runner logs symlink
    reactive_log_source = base_dir / "logs" / "reactive"
    _create_or_update_symlink(REACTIVE_RUNNER_LOG_SYMLINK, reactive_log_source)

    # Metrics log symlink
    metrics_log_source = base_dir / "logs" / "metrics" / "github-runner-metrics.log"
    _create_or_update_symlink(METRICS_LOG_SYMLINK, metrics_log_source)

    service_file_content = textwrap.dedent(
        f"""\
        [Unit]
        Description=Runs the github-runner-manager service
        StartLimitIntervalSec=0

        [Service]
        Type=simple
        User={constants.RUNNER_MANAGER_USER}
        Group={constants.RUNNER_MANAGER_GROUP}
        Environment="METRICS_LOG_PATH={METRICS_LOG_SYMLINK}"
        ExecStart=github-runner-manager --config-file {str(config_file)} \
--host {GITHUB_RUNNER_MANAGER_ADDRESS} --port {GITHUB_RUNNER_MANAGER_PORT} \
--python-path {str(python_path)} --log-level {log_level} --base-dir {str(base_dir)}
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
    GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH.write_text(service_file_content, "utf-8")


def _create_or_update_symlink(symlink_path: Path, source_path: Path) -> None:
    """Create or update a symlink to point to the source path.

    Args:
        symlink_path: The path where the symlink should be created.
        source_path: The path the symlink should point to.
    """
    # Create symlink if it doesn't exist or if it points to the wrong location
    if not symlink_path.exists() or not symlink_path.is_symlink():
        # Remove if it exists but is not a symlink (e.g., a directory or file)
        if symlink_path.exists():
            if symlink_path.is_dir():
                symlink_path.rmdir()
            else:
                symlink_path.unlink()
        symlink_path.symlink_to(source_path)
    elif symlink_path.resolve() != source_path.resolve():
        # Symlink exists but points to wrong location - update it
        symlink_path.unlink()
        symlink_path.symlink_to(source_path)
