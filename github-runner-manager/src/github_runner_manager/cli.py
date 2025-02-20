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

logging.basicConfig(level=logging.DEBUG)
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
)
@click.option(
    "--port",
    type=int,
    help="The port to listen on for the HTTP server.",
)
def main(config_file: TextIO, host: str, port: int) -> None:
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server.
        port: The port to listen on the HTTP server.
    """
    lock = Lock()
    config = Configuration.from_yaml_file(config_file)

    http_server = Thread(target=lambda: start_http_server(config, lock, host, port))
    http_server.start()
    service = Thread(target=lambda: start_reconcile_service(config, lock))
    service.start()

    http_server.join()
    service.join()


def start_reconcile_service(_: Configuration, lock: Lock) -> None:
    """Start the reconcile server.

    Args:
        lock: The lock representing modification access to the managed set of runners.
    """
    # The reconcile service is not implemented yet, current logging the lock status.
    while True:
        logger.info("lock acquired: %s", lock.locked())
        sleep(10)
