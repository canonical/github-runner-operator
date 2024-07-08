#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
import shutil
import subprocess
from pathlib import Path

from charm_state import ReactiveConfig
from utilities import secure_run_subprocess

logger = logging.getLogger(__name__)

REACTIVE_RUNNER_LOG_FILE = "/var/log/reactive_runner.log"
REACTIVE_RUNNER_SCRIPT_FILE = "scripts/reactive_runner.py"
REACTIVE_RUNNER_TIMEOUT_STR = "1h"
PYTHON_BIN = "/usr/bin/python3"
PS_COMMAND_LINE_LIST = ["ps", "axo", "cmd"]
TIMEOUT_COMMAND = "/usr/bin/timeout"
UBUNTU_USER = "ubuntu"


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


class ReactiveRunnerManager:
    """A class to manage the reactive runners."""

    def __init__(self, reactive_config: ReactiveConfig, queue_name: str):
        self._reactive_config = reactive_config
        self._queue_name = queue_name

    def reconcile(self, quantity: int) -> int:
        """Spawn a runner reactively.

        Args:
            queue_name: The name of the queue.

        Raises:
            ReactiveRunnerError: If the runner fails to spawn.
        """

        actual_quantity = self._determine_current_quantity()
        logger.info("Actual quantity of ReactiveRunner processes: %s", actual_quantity)
        delta = quantity - actual_quantity
        actual_delta = delta
        if delta > 0:
            logger.info("Will spawn %d new ReactiveRunner processes", delta)
            self._setup_log_file()
            for _ in range(delta):
                try:
                    self._spawn_runner()
                except ReactiveRunnerError:
                    logger.exception("Failed to spawn a new ReactiveRunner process")
                    actual_delta -= 1
        elif delta < 0:
            logger.info(
                "%d ReactiveRunner processes are running. Will skip spawning. Additional processes should terminate after %s.",
                actual_quantity,
                REACTIVE_RUNNER_TIMEOUT_STR,
            )
        else:
            logger.info("No changes to number of ReactiveRunners needed.")

        return max(actual_delta, 0)

    def _determine_current_quantity(self):
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

    def _setup_log_file(self) -> None:
        """Set up the log file."""
        logfile = Path(REACTIVE_RUNNER_LOG_FILE)
        if not logfile.exists():
            logfile.touch()
            shutil.chown(logfile, user=UBUNTU_USER, group=UBUNTU_USER)

    def _spawn_runner(self) -> None:
        """Spawn a runner."""
        env = {"PYTHONPATH": "src:lib:venv"}
        process = subprocess.Popen(
            [
                TIMEOUT_COMMAND,
                REACTIVE_RUNNER_TIMEOUT_STR,
                PYTHON_BIN,
                REACTIVE_RUNNER_SCRIPT_FILE,
                self._reactive_config.mq_uri,
                self._queue_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            user=UBUNTU_USER,
        )
        logger.debug("Spawned a new ReactiveRunner process with pid %s", process.pid)
        if process.returncode not in (0, None):
            raise ReactiveRunnerError("Failed to spawn a new ReactiveRunner process")
