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

import requests
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v1.systemd import SystemdError
from github_runner_manager import constants
from github_runner_manager.configuration.base import ApplicationConfiguration
from yaml import safe_dump as yaml_safe_dump

from charm_state import CharmState, PlannerConfig
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


def ensure_http_port_for_unit(unit_name: str) -> int:
    """Return the per-unit HTTP port, allocating and persisting if needed.

    The persisted per-unit port is used whenever available. If missing, a
    deterministic candidate derived from the unit index is probed for
    availability, falling back to scanning within a bounded range on
    collisions. Allocation is performed under a process-wide lock and written
    to disk before the lock is released to avoid concurrent units choosing the
    same port.

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

    Prefers the deterministic candidate derived from unit index. On collision,
    scans a small bounded range on 127.0.0.1 and avoids ports already
    persisted by other units. If all candidates are busy, returns the base
    port; systemd start will fail and surface error.
    """
    base = _deterministic_port_for_unit(unit_name)
    used_ports = _get_persisted_ports()
    if base not in used_ports and _port_available(GITHUB_RUNNER_MANAGER_ADDRESS, base):
        return base
    for offset in range(1, _PORT_SCAN_SPAN + 1):
        candidate = base + offset
        if candidate in used_ports:
            continue
        if _port_available(GITHUB_RUNNER_MANAGER_ADDRESS, candidate):
            return candidate
    logger.warning("No available port found for unit %s, using base port %d", unit_name, base)
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _get_persisted_ports() -> set[int]:
    """Return the set of ports persisted by all known units.

    This avoids transient races where another unit has persisted a port but
    has not started binding yet.

    Returns:
        A set of port numbers read from `http_port` files under the service dir.
    """
    ports: set[int] = set()
    try:
        for entry in GITHUB_RUNNER_MANAGER_SERVICE_DIR.iterdir():
            if not entry.is_dir():
                continue
            port_file = entry / "http_port"
            if not port_file.exists():
                continue
            try:
                ports.add(int(port_file.read_text(encoding="utf-8").strip()))
            except (ValueError, OSError):
                continue
    except FileNotFoundError:
        # Base dir may not exist yet.
        return set()
    return ports


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
    # NOTE: Cleanup of any legacy singleton service and stray processes is handled at the
    # charm layer (`_disable_legacy_service()`), so this setup routine focuses solely on
    # configuring and starting the per-unit instance service.
    instance_service = _instance_service_name(unit_name)
    try:
        if systemd.service_running(instance_service):
            systemd.service_stop(instance_service)
    except SystemdError as err:
        raise RunnerManagerApplicationStartError(_SERVICE_SETUP_ERROR_MESSAGE) from err

    if state.charm_config.planner is not None:
        planner_config = state.charm_config.planner
        _ensure_flavor(
            planner_config.endpoint,
            planner_config.token,
            planner_config.flavor,
            state.charm_config.labels,
            minimum_pressure=state.runner_config.base_virtual_machines,
        )

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


def cleanup_flavor(planner_config: PlannerConfig) -> None:
    """Clean up flavor from planner service when the relation is broken.

    Args:
        planner_config: The planner configuration.
    """
    _delete_flavor(planner_config.endpoint, planner_config.token, planner_config.flavor)


def _delete_flavor(endpoint: str, token: str, name: str) -> None:
    """Delete flavor from planner service.

    Args:
        endpoint: The planner service endpoint.
        token: The authentication token for the planner service.
        name: The flavor name.

    Raises:
        RunnerManagerApplicationStartError: If the delete request fails.
    """
    url = endpoint + f"/api/v1/flavors/{name}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.delete(url, headers=headers, timeout=10)
        response.raise_for_status()
    except (requests.RequestException, TimeoutError) as err:
        logger.exception("Failed to delete flavor %s from planner", name)
        raise RunnerManagerApplicationStartError("Failed to delete flavor from planner") from err


def _ensure_flavor(
    endpoint: str, token: str, name: str, labels: list[str], minimum_pressure: int
) -> None:
    """Ensure flavor exists in planner service.

    Args:
        endpoint: The planner service endpoint.
        token: The authentication token for the planner service.
        name: The flavor name.
        labels: The list of labels associated with the flavor.
        minimum_pressure: The minimum pressure for the flavor.

    Raises:
        RunnerManagerApplicationStartError: If the flavor check or creation fails.
    """
    url = endpoint + f"/api/v1/flavors/{name}"
    headers = {"Authorization": f"Bearer {token}"}
    desired_priority = 50
    try:
        get_response = requests.get(url, headers=headers, timeout=10)
        if get_response.status_code == 200:
            try:
                flavor = get_response.json()
            except ValueError as err:
                logger.exception("Failed to parse flavor %s from planner", name)
                raise RunnerManagerApplicationStartError(
                    "Failed to parse flavor from planner"
                ) from err
            actual_labels = flavor.get("labels") or []
            matches = (
                flavor.get("name") == name
                and flavor.get("platform") == "github"
                and sorted(actual_labels) == sorted(labels)
                and flavor.get("priority") == desired_priority
                and flavor.get("minimum_pressure") == minimum_pressure
            )
            if matches:
                return
            logger.info(
                "Flavor %s exists but does not match expected config; recreating", name
            )
            _delete_flavor(endpoint, token, name)
        elif get_response.status_code != 404:
            get_response.raise_for_status()
    except (requests.RequestException, TimeoutError) as err:
        logger.exception("Failed to check flavor %s on planner", name)
        raise RunnerManagerApplicationStartError("Failed to check flavor on planner") from err
    payload = {
        "name": name,
        "platform": "github",
        "labels": labels,
        "priority": desired_priority,
        "minimum_pressure": minimum_pressure,
    }
    try:
        post_response = requests.post(url, headers=headers, json=payload, timeout=10)
        post_response.raise_for_status()
    except (requests.RequestException, TimeoutError) as err:
        logger.exception("Failed to add flavor %s to planner", name)
        raise RunnerManagerApplicationStartError("Failed to add flavor to planner") from err


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
    """Enable and start the per-unit github runner manager service.

    Args:
        unit_name: The Juju unit name used to select the instance service.

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
    # NOTE: Port allocation and persistence are performed under a process-wide
    # lock in `ensure_http_port_for_unit()`; this returns a stable per-unit port.
    http_port = ensure_http_port_for_unit(unit_name)
    service_file_content = textwrap.dedent(f"""\
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
        """)
    service_path = (
        SYSTEMD_SERVICE_PATH / f"{GITHUB_RUNNER_MANAGER_SERVICE_NAME}@{instance}.service"
    )
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service_file_content, "utf-8")
