# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import logging
from threading import Lock, Thread
from time import sleep
from typing import TextIO

import click

from github_runner_manager.cli_config import Configuration
from github_runner_manager.http_server import start_http_server

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
        service = Thread(target=lambda: start_reconcile_service(config, lock))
        service.start()
        threads.append(service)
    http_server = Thread(target=lambda: start_http_server(config, lock, host, port, debug))
    http_server.start()
    threads.append(http_server)

    for thread in threads:
        thread.join()


# The reconcile logic is not implemented, therefore not unit tested.
def start_reconcile_service(_: Configuration, lock: Lock) -> None:  # pragma: no cover
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    # The reconcile service is not implemented yet, current logging the lock status.
    while True:
        logger.info("Lock locked: %s", lock.locked())
        logger.info("Reconcile: Attempting to acquire the lock...")
        with lock:
            logger.info("Reconcile: Sleeping a while...")
            sleep(10)
        logger.info("Reconcile: Released the lock")
