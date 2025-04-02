#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing processes which spawn runners reactively."""
import logging
import os
import shutil
import signal

# All commands run by subprocess are secure.
import subprocess  # nosec
from pathlib import Path

from github_runner_manager import constants
from github_runner_manager.configuration import UserInfo
from github_runner_manager.reactive.types_ import ReactiveProcessConfig
from github_runner_manager.utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

REACTIVE_RUNNER_LOG_DIR = Path("/var/log/reactive_runner")

PYTHON_BIN = "/usr/bin/python3"
REACTIVE_RUNNER_SCRIPT_MODULE = "github_runner_manager.reactive.runner"
REACTIVE_RUNNER_CMD_LINE_PREFIX = f"{PYTHON_BIN} -m {REACTIVE_RUNNER_SCRIPT_MODULE}"
PID_CMD_COLUMN_WIDTH = len(REACTIVE_RUNNER_CMD_LINE_PREFIX)
PIDS_COMMAND_LINE = [
    "ps",
    "axo",
    f"cmd:{PID_CMD_COLUMN_WIDTH},pid",
    "--no-headers",
    "--sort=-start_time",
]
UBUNTU_USER = "ubuntu"
RUNNER_CONFIG_ENV_VAR = "RUNNER_CONFIG"


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


def reconcile(
    quantity: int, reactive_process_config: ReactiveProcessConfig, user: UserInfo
) -> int:
    """Reconcile the number of reactive runner processes.

    Args:
        quantity: The number of processes to spawn.
        reactive_process_config: The reactive runner configuration.
        user: The user to run the reactive process.

    Raises a ReactiveRunnerError if the runner fails to spawn.

    Returns:
        The number of reactive runner processes spawned/killed.
    """
    pids = _get_pids()
    current_quantity = len(pids)
    logger.info("Current quantity of reactive runner processes: %s", current_quantity)
    delta = quantity - current_quantity
    if delta > 0:
        logger.info("Will spawn %d new reactive runner process(es)", delta)
        _setup_logging_for_processes(user.user, user.group)
        for _ in range(delta):
            _spawn_runner(reactive_process_config)
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

    # stdout will look like
    #
    # ps axo cmd:57,pid --no-headers --sort=-start_time         2302635
    # -bash                                                     2302498
    # /bin/sh -c /usr/bin/python3 -m github_runner_manager.reac 1757306
    # /usr/bin/python3 -m github_runner_manager.reactive.runner 1757308

    # we filter for the command line of the reactive runner processes and extract the PID

    return [
        int(line.rstrip().rsplit(maxsplit=1)[-1])
        for line in result.stdout.decode().split("\n")
        if line.startswith(REACTIVE_RUNNER_CMD_LINE_PREFIX)
    ]


def _setup_logging_for_processes(user: str, group: str) -> None:
    """Set up the log dir.

    Args:
        user: The user for logging.
        group: The group owning the logs.
    """
    REACTIVE_RUNNER_LOG_DIR.mkdir(exist_ok=True)
    shutil.chown(
        REACTIVE_RUNNER_LOG_DIR,
        user=user,
        group=group,
    )


def _spawn_runner(reactive_process_config: ReactiveProcessConfig) -> None:
    """Spawn a runner.

    Args:
        reactive_process_config: The runner configuration to pass to the spawned runner process.
    """
    env = {
        "PYTHONPATH": os.environ["PYTHONPATH"],
        RUNNER_CONFIG_ENV_VAR: reactive_process_config.json(),
    }
    # We do not want to wait for the process to finish, so we do not use with statement.
    # We trust the command.
    command = " ".join(
        [
            PYTHON_BIN,
            "-m",
            REACTIVE_RUNNER_SCRIPT_MODULE,
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
        user=constants.RUNNER_MANAGER_USER,
        group=constants.RUNNER_MANAGER_GROUP,
    )

    logger.info("Spawned a new reactive runner process with pid %s", process.pid)
