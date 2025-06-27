# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import logging
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
    "--python-path",
    type=str,
    default="",
    help="The PYTHONPATH to the github-runner-manager library.",
)
# The entry point for the CLI will be tested with integration test.
def main(
    config_file: TextIO,
    host: str,
    port: int,
    debug: bool,
    python_path: str,
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        python_path: The PYTHONPATH to access the github-runner-manager library.
    """
    python_path_config = python_path if python_path else None
    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

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
