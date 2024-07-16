#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing reactive runners."""
import logging
import shutil

# All commands run by subprocess are secure.
import subprocess  # nosec
from dataclasses import dataclass
from pathlib import Path

from logrotate import LogrotateConfig, LogrotateFrequency
from utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

MQ_URI_ENV_VAR = "MQ_URI"
REACTIVE_RUNNER_LOG_DIR = Path("/var/log/reactive_runner")
REACTIVE_RUNNER_SCRIPT_FILE = "scripts/reactive_runner.py"
REACTIVE_RUNNER_TIMEOUT_STR = "1h"
PYTHON_BIN = "/usr/bin/python3"
PS_COMMAND_LINE_LIST = ["ps", "axo", "cmd"]
TIMEOUT_COMMAND = "/usr/bin/timeout"
UBUNTU_USER = "ubuntu"

REACTIVE_LOGROTATE_CONFIG = LogrotateConfig(
    name="reactive-runner",
    log_path_glob_pattern=f"{REACTIVE_RUNNER_LOG_DIR}/.*",
    rotate=0,
    create=False,
    notifempty=False,
    frequency=LogrotateFrequency.DAILY,
)


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


@dataclass
class ReactiveRunnerConfig:
    """Configuration for spawning a reactive runner.

    Attributes:
        mq_uri: The message queue URI.
        queue_name: The name of the queue.
    """

    mq_uri: str
    queue_name: str


def reconcile(quantity: int, config: ReactiveRunnerConfig) -> int:
    """Spawn a runner reactively.

    Args:
        quantity: The number of runners to spawn.
        config: The configuration for the reactive runner.

    Raises a ReactiveRunnerError if the runner fails to spawn.

    Returns:
        The number of runners spawned.
    """
    actual_quantity = _determine_current_quantity()
    logger.info("Actual quantity of reactive runner processes: %s", actual_quantity)
    actual_delta = delta = quantity - actual_quantity
    if delta > 0:
        logger.info("Will spawn %d new reactive runner processes", delta)
        _setup_logging()
        for _ in range(delta):
            try:
                _spawn_runner(config)
            except _SpawnError:
                logger.exception("Failed to spawn a new reactive runner process")
        actual_quantity_after_spawning = _determine_current_quantity()
        actual_delta = actual_quantity_after_spawning - actual_quantity
    elif delta < 0:
        logger.info(
            "%d reactive runner processes are running. "
            "Will skip spawning. Additional processes should terminate after %s.",
            actual_quantity,
            REACTIVE_RUNNER_TIMEOUT_STR,
        )
    else:
        logger.info("No changes to number of reactive runner processes needed.")

    return max(actual_delta, 0)


def _determine_current_quantity() -> int:
    """Determine the current quantity of reactive runners.

    Returns:
        The number of reactive runners.

    Raises:
        ReactiveRunnerError: If the number of reactive runners cannot be determined
    """
    result = secure_run_subprocess(cmd=PS_COMMAND_LINE_LIST)
    if result.returncode != 0:
        raise ReactiveRunnerError("Failed to get list of processes")
    commands = result.stdout.decode().rstrip().split("\n")[1:] if result.stdout else []
    actual_quantity = 0
    for command in commands:
        if command.startswith(f"{PYTHON_BIN} {REACTIVE_RUNNER_SCRIPT_FILE}"):
            actual_quantity += 1
    return actual_quantity


def _setup_logging() -> None:
    """Set up the log dir."""
    if not REACTIVE_RUNNER_LOG_DIR.exists():
        REACTIVE_RUNNER_LOG_DIR.mkdir()
        shutil.chown(REACTIVE_RUNNER_LOG_DIR, user=UBUNTU_USER, group=UBUNTU_USER)


class _SpawnError(Exception):
    """Raised when spawning a runner fails."""


def _spawn_runner(reactive_runner_config: ReactiveRunnerConfig) -> None:
    """Spawn a runner.

    Args:
        reactive_runner_config: The configuration for the reactive runner.

    Raises:
        _SpawnError: If the runner fails to spawn.
    """
    env = {
        "PYTHONPATH": "src:lib:venv",
        MQ_URI_ENV_VAR: reactive_runner_config.mq_uri,
    }
    # We do not want to wait for the process to finish, so we do not use with statement.
    # We trust the command.
    command = " ".join(
        [
            TIMEOUT_COMMAND,
            REACTIVE_RUNNER_TIMEOUT_STR,
            PYTHON_BIN,
            REACTIVE_RUNNER_SCRIPT_FILE,
            f'"{reactive_runner_config.queue_name}"',
            ">>",
            # $$ will be replaced by the PID of the process, so we can track the error log easily.
            f"{REACTIVE_RUNNER_LOG_DIR}/$$.log",
            "2>&1",
        ]
    )
    logger.debug("Spawning a new reactive runner process with command: %s", command)
    process = subprocess.Popen(  # pylint: disable=consider-using-with  # nosec
        command,
        shell=True,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        user=UBUNTU_USER,
    )

    if process.returncode not in (0, None):
        raise _SpawnError(
            f"Failed to spawn a new reactive runner process with pid {process.pid}."
            f" Return code: {process.returncode}"
        )
    logger.debug("Spawned a new reactive runner process with pid %s", process.pid)
