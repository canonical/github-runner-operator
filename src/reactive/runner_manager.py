#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
import os
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

        result = secure_run_subprocess(cmd=["ps", "axo", "cmd"])
        if result.returncode != 0:
            raise ReactiveRunnerError("Failed to get list of processes")

        commands = result.stdout.decode().rstrip().split("\n")[1:]
        logger.info(commands)
        actual_quantity = 0
        for command in commands:
            if command.startswith(f"{PYTHON_BIN} {REACTIVE_RUNNER_SCRIPT_FILE}"):
                actual_quantity += 1
        logger.info("Actual quantity of ReactiveRunner processes: %s", actual_quantity)
        delta = quantity - actual_quantity
        if delta > 0:
            logger.info("Will spawn %d new ReactiveRunner processes", delta)
            self._setup_log_file()
            for _ in range(delta):
                self._spawn_runner()
        elif delta < 0:
            logger.info(
                "%d ReactiveRunner processes are running. Will skip spawning. Additional processes should terminate after %s.",
                actual_quantity,
                REACTIVE_RUNNER_TIMEOUT_STR,
            )
        else:
            logger.info("No changes to number of ReactiveRunners needed.")

        return max(delta, 0)


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
            # TODO: we are using devnull because there are hanging issues if we reuse the same fd as the parent
            # maybe add a check if the process is alive
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            user=UBUNTU_USER,
        )
        logger.debug("Spawned a new ReactiveRunner process with pid %s", process.pid)
