# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

from functools import partial
import logging
from threading import Lock, Thread
from typing import TextIO

import click

from github_runner_manager.cli_config import Configuration
from github_runner_manager.http_server import start_http_server
from github_runner_manager.reconcile_service import start_reconcile_service

logger = logging.getLogger(__name__)


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
    "--debug-disable-reconcile",
    is_flag=True,
    show_default=True,
    default=False,
    help="Disable reconcile thread for debugging.",
)
# The entry point for the CLI will be tested with integration test.
def main(
    config_file: TextIO, host: str, port: int, debug: bool, debug_disable_reconcile: bool
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server.
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        debug_disable_reconcile: Whether to not start the reconcile service for debugging.
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    lock = Lock()
    config = Configuration.from_yaml_file(config_file)

    threads = []
    if not debug_disable_reconcile:
        service = Thread(target=partial(start_reconcile_service, config, lock))
        service.start()
        threads.append(service)
    http_server = Thread(target=partial(start_http_server, config, lock, host, port, debug))
    http_server.start()
    threads.append(http_server)

    for thread in threads:
        thread.join()
