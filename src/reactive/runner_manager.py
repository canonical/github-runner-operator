#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing reactive runners."""
import logging
import shutil

# All commands run by subprocess are secure.
import subprocess  # nosec
from pathlib import Path

from utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

MQ_URI_ENV_VAR = "MQ_URI"
QUEUE_NAME_ENV_VAR = "QUEUE_NAME"
REACTIVE_RUNNER_LOG_DIR = Path("/var/log/reactive_runner")
REACTIVE_RUNNER_SCRIPT_FILE = "scripts/reactive_runner.py"
REACTIVE_RUNNER_TIMEOUT_INTERVAL = "1h"
PYTHON_BIN = "/usr/bin/python3"
ACTIVE_SCRIPTS_COMMAND_LINE = ["ps", "axo", "cmd", "--no-headers"]
TIMEOUT_BIN = "/usr/bin/timeout"
UBUNTU_USER = "ubuntu"


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


def reconcile(quantity: int, mq_uri: str, queue_name: str) -> int:
    """Spawn a runner reactively.

    Args:
        quantity: The number of runners to spawn.
        mq_uri: The message queue URI.
        queue_name: The name of the queue.

    Raises a ReactiveRunnerError if the runner fails to spawn.

    Returns:
        The number of reactive runner processes spawned.
    """
    current_quantity = _get_current_quantity()
    logger.info("Current quantity of reactive runner processes: %s", current_quantity)
    delta = quantity - current_quantity
    if delta > 0:
        logger.info("Will spawn %d new reactive runner processes", delta)
        _setup_logging_for_processes()
        for _ in range(delta):
            _spawn_runner(mq_uri=mq_uri, queue_name=queue_name)
    elif delta < 0:
        logger.info(
            "%d reactive runner processes are running. "
            "Will skip spawning. Additional processes should terminate after %s.",
            current_quantity,
            REACTIVE_RUNNER_TIMEOUT_INTERVAL,
        )
    else:
        logger.info("No changes to number of reactive runner processes needed.")

    return max(delta, 0)


def _get_current_quantity() -> int:
    """Determine the current quantity of reactive runners.

    Returns:
        The number of reactive runners.

    Raises:
        ReactiveRunnerError: If the number of reactive runners cannot be determined
    """
    result = secure_run_subprocess(cmd=ACTIVE_SCRIPTS_COMMAND_LINE)
    if result.returncode != 0:
        raise ReactiveRunnerError("Failed to get list of processes")
    commands = result.stdout.decode().split("\n") if result.stdout else []
    return sum(
        1
        for command in commands
        if command.startswith(f"{PYTHON_BIN} {REACTIVE_RUNNER_SCRIPT_FILE}")
    )


def _setup_logging_for_processes() -> None:
    """Set up the log dir."""
    if not REACTIVE_RUNNER_LOG_DIR.exists():
        REACTIVE_RUNNER_LOG_DIR.mkdir()
        shutil.chown(REACTIVE_RUNNER_LOG_DIR, user=UBUNTU_USER, group=UBUNTU_USER)


def _spawn_runner(mq_uri: str, queue_name: str) -> None:
    """Spawn a runner.

    Args:
        mq_uri: The message queue URI.
        queue_name: The name of the queue.
    """
    env = {
        "PYTHONPATH": "src:lib:venv",
        MQ_URI_ENV_VAR: mq_uri,
        QUEUE_NAME_ENV_VAR: queue_name,
    }
    # We do not want to wait for the process to finish, so we do not use with statement.
    # We trust the command.
    command = " ".join(
        [
            TIMEOUT_BIN,
            REACTIVE_RUNNER_TIMEOUT_INTERVAL,
            PYTHON_BIN,
            REACTIVE_RUNNER_SCRIPT_FILE,
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

    logger.info("Spawned a new reactive runner process with pid %s", process.pid)
