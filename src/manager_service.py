#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Manage the service of github-runner-manager."""

import json
from pathlib import Path

import jinja2
import yaml
from charms.operator_libs_linux.v1 import systemd
from github_runner_manager import constants

from charm_state import CharmState
from errors import (
    RunnerManagerApplicationInstallError,
    RunnerManagerApplicationStartupError,
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
GITHUB_RUNNER_MANAGER_SERVICE_NAME = "github-runner-manager"


def setup(state: CharmState, app_name: str, unit_name: str) -> None:
    """Set up the github-runner-manager service.

    Args:
        state: The state of the charm.
        app_name: The Juju application name.
        unit_name: The Juju unit.
    """
    config_file = _setup_config_file(state, app_name, unit_name)
    _setup_service_file(config_file)
    _enable_service()


def install_github_runner_manager() -> None:
    """Install the GitHub runner manager package.

    Raises:
        RunnerManagerApplicationInstallError: Unable to install the application.
    """
    try:
        execute_command(["python3", "-m", "pip", "install", "--upgrade", "pip"])
        # Use `--prefix` to install the package in a location (/usr) all user can use and
        # `--ignore-installed` to force all dependencies be to installed under /usr.
        execute_command(
            [
                "python3",
                "-m",
                "pip",
                "install",
                "--prefix",
                "/usr",
                "--ignore-installed",
                f"./{GITHUB_RUNNER_MANAGER_SERVICE_NAME}",
            ]
        )
    except SubprocessError as err:
        raise RunnerManagerApplicationInstallError(
            "Unable to install github-runner-manager package from source"
        ) from err


def _enable_service() -> None:
    """Enable the github runner manager service.

    Raises:
        RunnerManagerApplicationStartupError: Unable to startup the service.
    """
    try:
        systemd.service_enable(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
        if not systemd.service_running(GITHUB_RUNNER_MANAGER_SERVICE_NAME):
            systemd.service_start(GITHUB_RUNNER_MANAGER_SERVICE_NAME)
    except systemd.SystemdError as err:
        raise RunnerManagerApplicationStartupError(
            "Unable to enable or start the github-runner-manager application"
        ) from err


def _setup_config_file(state: CharmState, app_name: str, unit_name: str) -> Path:
    """Write the configuration to file.

    Args:
        state: The charm state.
        app_name: The Juju application name.
        unit_name: The Juju unit.
    """
    config = create_application_configuration(state, app_name, unit_name)
    # Directly converting to `dict` will have the value be Python objects rather than string
    # representations. The values needs to be string representations to be converted to YAML file.
    # No easy way to directly convert to YAML file, so json module is used.
    config_dict = json.loads(config.json())
    path = Path(f"~{constants.RUNNER_MANAGER_USER}").expanduser() / "config.yaml"
    with open(path, "w+", encoding="utf-8") as file:
        yaml.safe_dump(config_dict, file)
    return path


def _setup_service_file(config_file: Path) -> None:
    """Configure the systemd service.

    Args:
        config_file: The configuration file for the service.
    """
    jinja = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)

    service_file_content = jinja.get_template("github-runner-manager.service.j2").render(
        user=constants.RUNNER_MANAGER_USER,
        group=constants.RUNNER_MANAGER_GROUP,
        config=str(config_file),
        host=GITHUB_RUNNER_MANAGER_ADDRESS,
        port=GITHUB_RUNNER_MANAGER_PORT,
    )

    GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH.write_text(service_file_content, "utf-8")
