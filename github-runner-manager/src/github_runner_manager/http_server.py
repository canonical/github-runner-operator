#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The HTTP server for github-runner-manager.

The HTTP server for request to the github-runner-manager.
"""

from threading import Lock

from flask import Flask, request

from github_runner_manager.cli_config import Configuration

app = Flask(__name__)

_lock: Lock

@app.route("/health", methods=["GET"])
def get_health() -> tuple[str, int]:
    """Get the health of the HTTP server.

    Returns:
        A empty response.
    """
    return ("", 204)


@app.route("/runner/flush", methods=["POST"])
def flush_runner() -> tuple[str, int]:
    """Flush the runners.

    The logic of this function will be implemented in a future PR.

    HTTP header args:
        flush-busy(bool): Whether to flush busy runners.

    Returns:
        A empty response.
    """
    flush_busy = request.headers.get("flush-busy")
    if flush_busy in ("True", "true"):
        app.logger.info("Flushing busy runners...")
    else:
        app.logger.info("Flushing idle runners...")

    app.logger.info("Lock locked: %s", _lock.locked())
    app.logger.info("Flush: Attempting to acquire the lock...")
    with _lock:
        app.logger.info("Flushing the runners")
    app.logger.info("Flushed the runners")
    return ("", 204)


def start_http_server(_: Configuration, lock: Lock, host: str, port: int, debug: bool) -> None:
    """Start the HTTP server for interacting with the github-runner-manager service.

    Args:
        lock: The lock representing modification access to the managed set of runners.
        host: The hostname to listen on for the HTTP server.
        port: The port to listen on for the HTTP server.
        debug: Start the flask HTTP server in debug mode.
    """
    global _lock
    _lock = lock
    app.run(host=host, port=port, debug=debug, use_reloader=False)
