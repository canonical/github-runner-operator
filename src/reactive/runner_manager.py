#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing reactive runners."""
import logging
import os
import shutil
import signal

# All commands run by subprocess are secure.
import subprocess  # nosec
from pathlib import Path

from pydantic import MongoDsn

from utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

MQ_URI_ENV_VAR = "MQ_URI"
QUEUE_NAME_ENV_VAR = "QUEUE_NAME"
REACTIVE_RUNNER_LOG_DIR = Path("/var/log/reactive_runner")
REACTIVE_RUNNER_SCRIPT_FILE = "scripts/reactive_runner.py"
PYTHON_BIN = "/usr/bin/python3"
REACTIVE_RUNNER_CMD_LINE_PREFIX = f"{PYTHON_BIN} {REACTIVE_RUNNER_SCRIPT_FILE}"
PID_CMD_COLUMN_WIDTH = len(REACTIVE_RUNNER_CMD_LINE_PREFIX)
PIDS_COMMAND_LINE = [
    "ps",
    "axo",
    f"cmd:{PID_CMD_COLUMN_WIDTH},pid",
    "--no-headers",
    "--sort=-start_time",
]
UBUNTU_USER = "ubuntu"


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


def reconcile(quantity: int, mq_uri: MongoDsn, queue_name: str) -> int:
    """Spawn a runner reactively.

    Args:
        quantity: The number of runners to spawn.
        mq_uri: The message queue URI.
        queue_name: The name of the queue.

    Raises a ReactiveRunnerError if the runner fails to spawn.

    Returns:
        The number of reactive runner processes spawned.
    """
    pids = _get_pids()
    current_quantity = len(pids)
    logger.info("Current quantity of reactive runner processes: %s", current_quantity)
    delta = quantity - current_quantity
    if delta > 0:
        logger.info("Will spawn %d new reactive runner process(es)", delta)
        _setup_logging_for_processes()
        for _ in range(delta):
            _spawn_runner(mq_uri=mq_uri, queue_name=queue_name)
    elif delta < 0:
        logger.info("Will kill %d process(es).", -delta)
        for pid in pids[:-delta]:
            logger.info("Killing reactive runner process with pid %s", pid)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                # There can be a race condition that the process has already terminated.
                # We just ignore and log the fact.
                logger.info(
                    "Failed to kill process with pid %s. Process might have terminated it self.",
                    pid,
                )
    else:
        logger.info("No changes to number of reactive runner processes needed.")

    return delta


def _get_pids() -> list[int]:
    """Get the PIDs of the reactive runners processes.

    Returns:
        The PIDs of the reactive runner processes sorted by start time in descending order.

    Raises:
        ReactiveRunnerError: If the command to get the PIDs fails
    """
    result = secure_run_subprocess(cmd=PIDS_COMMAND_LINE)
    if result.returncode != 0:
        raise ReactiveRunnerError("Failed to get list of processes")

    return [
        int(line.rstrip().rsplit(maxsplit=1)[-1])
        for line in result.stdout.decode().split("\n")
        if line.startswith(REACTIVE_RUNNER_CMD_LINE_PREFIX)
    ]


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
