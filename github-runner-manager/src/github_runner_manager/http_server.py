from flask import Flask
from threading import Lock

from github_runner_manager.cli_config import Configuration

app = Flask(__name__)


# The path under /lock are for integration testing.
@app.route("/lock/status")
def lock_status():
    """Returns status of the lock.

    This is for integration tests.    

    Returns:
        Whether the lock is locked.
    """
    return ("locked", 200) if _get_lock().locked() else ("unlocked", 200)

@app.route("/lock/acquire")
def lock_acquire():
    """Acquire the thread lock.

    This is for integration tests.
    """
    _get_lock().acquire(blocking=True)
    return ("", 200)

@app.route("/lock/release")
def lock_release():
    """Release the thread lock.

    This is for integration tests.
    """
    _get_lock().release()
    return ("", 200)

def _get_lock() -> Lock:
    """Get the thread lock.
    
    Returns:
        The thread lock.
    """
    return app.config["lock"]

def start_http_server(_: Configuration, lock: Lock, host: str, port: int) -> None:
    """Start the HTTP server for interacting with the github-runner-manager service."""
    app.config['lock'] = lock
    app.run(host=host, port=port, use_reloader=False)
