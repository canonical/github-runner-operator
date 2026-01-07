# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import importlib.metadata
import logging
import os
from functools import partial
from io import StringIO
from pathlib import Path
from threading import Lock
from typing import TextIO

import click

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.http_server import FlaskArgs, start_http_server
from github_runner_manager.reconcile_service import start_reconcile_service
from github_runner_manager.thread_manager import ThreadManager

version = importlib.metadata.version("github-runner-manager")


def _resolve_log_path(log_path: str | None) -> Path:
    """Resolve the full log file path based on input/XDG defaults.

    Args:
        log_path: Optional user-provided log directory path.

    Returns:
        The resolved full path to the application log file (manager.log).
    """
    if log_path is None:
        xdg_state_home = os.environ.get("XDG_STATE_HOME")
        base_state = Path(xdg_state_home) if xdg_state_home else Path.home() / ".local" / "state"
        return base_state / "github-runner" / "logs" / "manager.log"
    return Path(log_path) / "manager.log"


def _ensure_log_path(log_path: str | None) -> Path:
    """Resolve and validate the log file path, ensuring directories exist.

    This will create the parent directories if needed and verify the directory
    is writable. Returns the full path to the log file.

    Args:
        log_path: Optional user-provided log directory path.

    Returns:
        Path to the log file.

    Raises:
        click.ClickException: If the path cannot be created or is not writable.
    """
    file_path = _resolve_log_path(log_path)
    parent = file_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise click.ClickException(f"Cannot create log directory: {parent} ({exc})") from exc
    if parent.is_file():
        raise click.ClickException(f"Expected a directory for logs but found a file: {parent}")
    if not os.access(parent, os.W_OK):
        raise click.ClickException(f"Log directory is not writable: {parent}")
    return file_path


@click.command()
@click.option(
    "--config-file",
    type=click.File(mode="r", encoding="utf-8"),
    help="The file path containing the configurations.",
)
@click.option(
    "--host",
    type=str,
    help="The hostname to listen on for the HTTP server.",
    default="127.0.0.1",
)
@click.option(
    "--port",
    type=int,
    help="The port to listen on for the HTTP server.",
    default=8080,
)
@click.option(
    "--debug",
    is_flag=True,
    show_default=True,
    default=False,
    help="Debug mode for testing.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        [
            "CRITICAL",
            "FATAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        ]
    ),
    default="INFO",
    help="The log level for the application.",
)
@click.option(
    "--log-path",
    type=click.Path(file_okay=False, dir_okay=True, writable=True, resolve_path=True),
    default=None,
    help=(
        "Directory to write application logs. Defaults to "
        "XDG_STATE_HOME/github-runner/logs (or ~/.local/state/github-runner/logs)."
    ),
)
@click.option(
    "--python-path",
    type=str,
    default="",
    help="The PYTHONPATH to the github-runner-manager library.",
)
# The entry point for the CLI will be tested with integration test.
def main(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    config_file: TextIO,
    host: str,
    port: int,
    debug: bool,
    log_level: str,
    log_path: str | None,
    python_path: str,
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        log_level: The log level.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        log_path: Directory to write application logs; defaults to XDG path.
    """
    log_file = _ensure_log_path(log_path)

    python_path_config = python_path if python_path else None
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    logging.basicConfig(
        level=log_level,
        handlers=[file_handler],
        force=True,
    )
    logging.info("Starting GitHub runner manager service version: %s", version)

    lock = Lock()
    config_str = config_file.read()
    config = ApplicationConfiguration.from_yaml_file(StringIO(config_str))
    http_server_args = FlaskArgs(host=host, port=port, debug=debug)

    thread_manager = ThreadManager()
    thread_manager.add_thread(
        target=partial(start_http_server, config, lock, http_server_args), daemon=True
    )
    thread_manager.add_thread(
        target=partial(start_reconcile_service, config, python_path_config, lock), daemon=True
    )
    thread_manager.start()

    thread_manager.raise_on_error()
