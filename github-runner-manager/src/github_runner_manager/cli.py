# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import importlib.metadata
import logging
import os
import sys
from functools import partial
from io import StringIO
from threading import Lock
from typing import TextIO

import click

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.http_server import FlaskArgs, start_http_server
from github_runner_manager.reconcile_service import start_reconcile_service
from github_runner_manager.thread_manager import ThreadManager
from github_runner_manager.utilities import get_base_dir, set_env_var

version = importlib.metadata.version("github-runner-manager")


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
    "--python-path",
    type=str,
    default=None,
    help="The PYTHONPATH to the github-runner-manager library.",
)
@click.option(
    "--base-dir",
    type=str,
    default=None,
    help=(
        "Base directory for all application data (state, logs, metrics). "
        "If not set, uses GITHUB_RUNNER_MANAGER_BASE_DIR env var or defaults to "
        "$XDG_STATE_HOME/github-runner-manager or ~/.local/state/github-runner-manager."
    ),
)
# The entry point for the CLI will be tested with integration test.
def main(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    config_file: TextIO,
    host: str,
    port: int,
    debug: bool,
    log_level: str,
    python_path: str | None,
    base_dir: str | None,
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        log_level: The log level.
        python_path: The PYTHONPATH to access the github-runner-manager library.
        base_dir: The base directory for all application data.
    """
    python_path_config = python_path
    base_dir_config = base_dir
    resolved_base_dir = str(get_base_dir(base_dir_config))

    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Starting GitHub runner manager service version: %s", version)

    # Export base dir for modules using base-dir convention (e.g., utilities.get_base_dir).
    if not os.environ.get("GITHUB_RUNNER_MANAGER_BASE_DIR"):
        set_env_var("GITHUB_RUNNER_MANAGER_BASE_DIR", resolved_base_dir)

    lock = Lock()
    config_str = config_file.read()
    config = ApplicationConfiguration.from_yaml_file(StringIO(config_str))
    http_server_args = FlaskArgs(host=host, port=port, debug=debug)

    thread_manager = ThreadManager()
    thread_manager.add_thread(
        target=partial(start_http_server, config, lock, http_server_args), daemon=True
    )
    thread_manager.add_thread(
        target=partial(
            start_reconcile_service,
            config,
            python_path_config,
            lock,
            resolved_base_dir,
        ),
        daemon=True,
    )
    thread_manager.start()

    thread_manager.raise_on_error()
