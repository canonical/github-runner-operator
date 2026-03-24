#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The HTTP server for github-runner-manager."""

import json
from dataclasses import dataclass
from threading import Lock

from flask import Flask, request
from prometheus_client import generate_latest

from github_runner_manager.errors import CloudError, LockError
from github_runner_manager.manager.runner_manager import FlushMode, RunnerManager

RUNNER_MANAGER_CONFIG_NAME = "runner_manager"

app = Flask(__name__)

# Pylint thinks this is a constant which needs to be upper case. This is a global variable.
_lock = None  # pylint: disable=invalid-name


@app.route("/health", methods=["GET"])
def get_health() -> tuple[str, int]:
    """Get the health of the HTTP server.

    Returns:
        A empty response.
    """
    return ("", 204)


@app.route("/runner/check", methods=["GET"])
def check_runner() -> tuple[str, int]:
    """Check the runners.

    Returns:
        Information on the runners in JSON format.
    """
    runner_manager: RunnerManager = app.config[RUNNER_MANAGER_CONFIG_NAME]
    app.logger.info("Checking runners...")
    try:
        runner_info = runner_manager.get_runner_info()
    except CloudError as err:
        app.logger.exception("Cloud error encountered while getting runner info")
        return (str(err), 500)

    response = {
        "online": runner_info.online,
        "busy": runner_info.busy,
        "offline": runner_info.offline,
        "unknown": runner_info.unknown,
        "runners": list(runner_info.runners),
        "busy_runners": list(runner_info.busy_runners),
    }
    return (json.dumps(response), 200)


@app.route("/runner/flush", methods=["POST"])
def flush_runner() -> tuple[str, int]:
    """Flush the runners.

    HTTP path args:
        flush-busy(bool): Whether to flush busy runners.

    Returns:
        A empty response.
    """
    runner_manager: RunnerManager = app.config[RUNNER_MANAGER_CONFIG_NAME]

    flush_busy_str = request.args.get("flush-busy")
    flush_busy = False
    if flush_busy_str in ("True", "true"):
        flush_busy = True

    lock = _get_lock()
    with lock:
        app.logger.info("Flushing runners...")
        app.logger.info("Flushing busy: %s", flush_busy)
        flush_mode = FlushMode.FLUSH_BUSY if flush_busy else FlushMode.FLUSH_IDLE
        try:
            runner_manager.flush_runners(flush_mode)
        except CloudError as err:
            app.logger.exception("Cloud error encountered while flushing runners")
            return (str(err), 500)
    return ("", 204)


def _get_lock() -> Lock:
    """Get the lock representing modification access to the set of runners.

    Raises:
        LockError: The lock is missing.

    Returns:
        The lock.
    """
    if _lock is not None:
        lock_state = "locked" if _lock.locked() else "unlocked"
        app.logger.info("Attempting to acquire the lock: %s", lock_state)
        return _lock
    raise LockError("Lock not configured")


@app.route("/metrics", methods=["GET"])
def metrics() -> bytes:
    """Return prometheus metrics from default registry.

    Returns:
        The latest metrics from the default Prometheus registry.
    """
    return generate_latest()


@dataclass
class FlaskArgs:
    """Arguments for Flask HTTP server.

    Attributes:
        host: The hostname to listen on for the HTTP server.
        port: The port to listen on for the HTTP server.
        debug: Start the flask HTTP server in debug mode.
    """

    host: str
    port: int
    debug: bool


def start_http_server(
    runner_manager: RunnerManager,
    lock: Lock,
    flask_args: FlaskArgs,
) -> None:
    """Start the HTTP server for interacting with the github-runner-manager service.

    Args:
        runner_manager: The runner manager for managing runners.
        lock: The lock representing modification access to the managed set of runners.
        flask_args: The arguments for the flask HTTP server.
    """
    app.logger.info("Starting the server...")
    # The lock is passed from the caller, hence the need to update the global variable.
    global _lock  # pylint: disable=global-statement
    _lock = lock
    app.config[RUNNER_MANAGER_CONFIG_NAME] = runner_manager
    app.run(
        host=flask_args.host,
        port=flask_args.port,
        debug=flask_args.debug,
        use_reloader=False,
    )
