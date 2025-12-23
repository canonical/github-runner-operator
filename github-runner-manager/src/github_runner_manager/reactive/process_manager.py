#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for managing processes which spawn runners reactively."""
import logging
import os
import shutil
import signal

# All commands run by subprocess are secure.
import subprocess  # nosec
import sys
from pathlib import Path

from github_runner_manager import constants
from github_runner_manager.configuration import UserInfo
from github_runner_manager.reactive.types_ import ReactiveProcessConfig
from github_runner_manager.utilities import get_state_dir, secure_run_subprocess

logger = logging.getLogger(__name__)

REACTIVE_RUNNER_SCRIPT_MODULE = "github_runner_manager.reactive.runner"
UBUNTU_USER = "ubuntu"
RUNNER_CONFIG_ENV_VAR = "RUNNER_CONFIG"


def _get_reactive_log_dir(reactive_log_dir: str | None = None) -> Path:
    """Get the reactive runner log directory.

    Args:
        reactive_log_dir: Optional explicit reactive log directory path.

    Returns:
        The resolved reactive log directory path.
    """
    # Check explicit parameter first
    if reactive_log_dir:
        return Path(reactive_log_dir).expanduser().resolve()

    # Check environment variable
    env_log_dir = os.getenv("GITHUB_RUNNER_MANAGER_REACTIVE_LOG_DIR")
    if env_log_dir:
        return Path(env_log_dir).expanduser().resolve()

    # Default to state_dir/reactive_runner
    state_dir = get_state_dir()
    return state_dir / "reactive_runner"


def _get_python_bin() -> str:
    """Get the Python interpreter to use for reactive processes.

    Returns the current Python interpreter (sys.executable) to ensure
    reactive subprocesses use the same Python environment as the parent.

    Returns:
        The path to the Python interpreter.
    """
    return sys.executable


# Update these dynamically based on the Python binary
def _get_pids_command(python_bin: str) -> list[str]:
    """Get the ps command to find reactive runner processes.

    Args:
        python_bin: The Python binary path to search for.

    Returns:
        The ps command list.
    """
    cmd_prefix = f"{python_bin} -m {REACTIVE_RUNNER_SCRIPT_MODULE}"
    cmd_column_width = len(cmd_prefix)
    return [
        "ps",
        "axo",
        f"cmd:{cmd_column_width},pid",
        "--no-headers",
        "--sort=-start_time",
    ]


class ReactiveRunnerError(Exception):
    """Raised when a reactive runner error occurs."""


def reconcile(
    quantity: int,
    reactive_process_config: ReactiveProcessConfig,
    user: UserInfo,
    python_path: str | None = None,
    reactive_log_dir: str | None = None,
) -> int:
    """Reconcile the number of reactive runner processes.

    Args:
        quantity: The number of processes to spawn.
        reactive_process_config: The reactive runner configuration.
        user: The user to run the reactive process.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        reactive_log_dir: The directory for reactive runner logs.

    Raises a ReactiveRunnerError if the runner fails to spawn.

    Returns:
        The number of reactive runner processes spawned/killed.
    """
    python_bin = _get_python_bin()
    pids = _get_pids(python_bin)
    current_quantity = len(pids)
    logger.info(
        "Reactive runner processes: current quantity %s, expected quantity %s",
        current_quantity,
        quantity,
    )
    delta = quantity - current_quantity
    if delta > 0:
        logger.info("Will spawn %d new reactive runner process(es)", delta)
        log_dir = _get_reactive_log_dir(reactive_log_dir)
        _setup_logging_for_processes(log_dir, user.user, user.group)
        for _ in range(delta):
            _spawn_runner(reactive_process_config, python_path, python_bin, log_dir)
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


def kill_reactive_processes() -> None:
    """Kill all reactive processes."""
    python_bin = _get_python_bin()
    pids = _get_pids(python_bin)
    if pids:
        for pid in pids:
            try:
                logger.info("Killing reactive runner process with pid %s", pid)
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                logger.info(
                    "Failed to kill process with pid %s. Process might have terminated it self.",
                    pid,
                )
    else:
        logger.info("No reactive processes to flush")


def _get_pids(python_bin: str) -> list[int]:
    """Get the PIDs of the reactive runners processes.

    Args:
        python_bin: The Python binary path to search for.

    Returns:
        The PIDs of the reactive runner processes sorted by start time in descending order.

    Raises:
        ReactiveRunnerError: If the command to get the PIDs fails
    """
    pids_command = _get_pids_command(python_bin)
    result = secure_run_subprocess(cmd=pids_command)
    if result.returncode != 0:
        raise ReactiveRunnerError("Failed to get list of processes")

    # stdout will look like
    #
    # ps axo cmd:57,pid --no-headers --sort=-start_time         2302635
    # -bash                                                     2302498
    # /bin/sh -c /usr/bin/python3 -m github_runner_manager.reac 1757306
    # /usr/bin/python3 -m github_runner_manager.reactive.runner 1757308

    # we filter for the command line of the reactive runner processes and extract the PID

    cmd_prefix = f"{python_bin} -m {REACTIVE_RUNNER_SCRIPT_MODULE}"
    return [
        int(line.rstrip().rsplit(maxsplit=1)[-1])
        for line in result.stdout.decode().split("\n")
        if line.startswith(cmd_prefix)
    ]


def _setup_logging_for_processes(log_dir: Path, user: str, group: str) -> None:
    """Set up the log dir.

    Args:
        log_dir: The directory for logs.
        user: The user for logging.
        group: The group owning the logs.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Only attempt to chown if running as root (has appropriate privileges)
    try:
        if os.geteuid() == 0:
            shutil.chown(log_dir, user=user, group=group)
            logger.debug("Set ownership of %s to %s:%s", log_dir, user, group)
        else:
            logger.debug(
                "Not running as root, skipping chown of %s (will use current user permissions)",
                log_dir,
            )
    except (PermissionError, OSError) as exc:
        logger.warning(
            "Failed to set ownership of %s, continuing with current permissions: %s",
            log_dir,
            exc,
        )


def _spawn_runner(
    reactive_process_config: ReactiveProcessConfig,
    python_path: str | None,
    python_bin: str,
    log_dir: Path,
) -> None:
    """Spawn a runner.

    Args:
        reactive_process_config: The runner configuration to pass to the spawned runner process.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        python_bin: The Python interpreter to use.
        log_dir: The directory for logs.
    """
    env = {
        RUNNER_CONFIG_ENV_VAR: reactive_process_config.json(),
    }
    if python_path is not None:
        env["PYTHONPATH"] = str(python_path)
    # We do not want to wait for the process to finish, so we do not use with statement.
    # We trust the command.
    command = " ".join(
        [
            python_bin,
            "-m",
            REACTIVE_RUNNER_SCRIPT_MODULE,
            ">>",
            # $$ will be replaced by the PID of the process, so we can track the error log easily.
            f"{log_dir}/$$.log",
            "2>&1",
        ]
    )
    logger.debug("Spawning a new reactive runner process with command: %s", command)
    
    # Only set user/group if running as root
    popen_kwargs = {
        "shell": True,
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    
    if os.geteuid() == 0:
        # Running as root, can set user and group
        popen_kwargs["user"] = constants.RUNNER_MANAGER_USER
        popen_kwargs["group"] = constants.RUNNER_MANAGER_GROUP
        logger.debug(
            "Running as root, spawning process as %s:%s",
            constants.RUNNER_MANAGER_USER,
            constants.RUNNER_MANAGER_GROUP,
        )
    else:
        logger.debug("Not running as root, spawning process as current user")
    
    process = subprocess.Popen(  # pylint: disable=consider-using-with  # nosec
        command,
        **popen_kwargs,
    )

    logger.info("Spawned a new reactive runner process with pid %s", process.pid)
