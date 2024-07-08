#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing reactive runners."""
import logging
import shutil

# All commands run by subprocess are secure.
import subprocess  # nosec
from dataclasses import dataclass
from pathlib import Path

from utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

REACTIVE_RUNNER_LOG_PATH = "/var/log/reactive_runner.log"
REACTIVE_RUNNER_SCRIPT_FILE = "scripts/reactive_runner.py"
REACTIVE_RUNNER_TIMEOUT_STR = "1h"
PYTHON_BIN = "/usr/bin/python3"
PS_COMMAND_LINE_LIST = ["ps", "axo", "cmd"]
TIMEOUT_COMMAND = "/usr/bin/timeout"
UBUNTU_USER = "ubuntu"


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
    delta = quantity - actual_quantity
    actual_delta = delta
    if delta > 0:
        logger.info("Will spawn %d new reactive runner processes", delta)
        _setup_log_file()
        for _ in range(delta):
            try:
                _spawn_runner(config)
            except ReactiveRunnerError:
                logger.exception("Failed to spawn a new reactive runner process")
                actual_delta -= 1
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
    commands = result.stdout.decode().rstrip().split("\n")[1:]
    logger.debug(commands)
    actual_quantity = 0
    for command in commands:
        if command.startswith(f"{PYTHON_BIN} {REACTIVE_RUNNER_SCRIPT_FILE}"):
            actual_quantity += 1
    return actual_quantity


def _setup_log_file() -> None:
    """Set up the log file."""
    logfile = Path(REACTIVE_RUNNER_LOG_PATH)
    if not logfile.exists():
        logfile.touch()
        shutil.chown(logfile, user=UBUNTU_USER, group=UBUNTU_USER)


def _spawn_runner(reactive_runner_config: ReactiveRunnerConfig) -> None:
    """Spawn a runner.

    Args:
        reactive_runner_config: The configuration for the reactive runner.

    Raises:
        ReactiveRunnerError: If the runner fails to spawn.
    """
    env = {"PYTHONPATH": "src:lib:venv"}
    # We do not want to wait for the process to finish, so we do not use with statement.
    # We trust the command.
    process = subprocess.Popen(  # pylint: disable=consider-using-with  # nosec
        [
            TIMEOUT_COMMAND,
            REACTIVE_RUNNER_TIMEOUT_STR,
            PYTHON_BIN,
            REACTIVE_RUNNER_SCRIPT_FILE,
            reactive_runner_config.mq_uri,
            reactive_runner_config.queue_name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        user=UBUNTU_USER,
    )
    logger.debug("Spawned a new reactive runner process with pid %s", process.pid)
    if process.returncode not in (0, None):
        raise ReactiveRunnerError(
            f"Failed to spawn a new reactive runner process. Return code: {process.returncode}"
        )
