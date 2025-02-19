# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import datetime
import logging
from threading import Lock, Thread
from time import sleep
from typing import TextIO

import click

from github_runner_manager.cli_config import Configuration
from github_runner_manager.http_server import start_http_server

logger = logging.getLogger(__name__)


# The entry point for the CLI will be tested with integration test.
@click.command()
@click.option(
    "--config-file",
    type=click.File(mode="r", encoding="utf-8"),
    help="The file path containing the configurations.",
)
def main(config_file: TextIO) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.

    Raises:
        NotImplementedError: The github runner manager logic is not yet implemented.
    """
    lock = Lock()
    config = Configuration.from_yaml_file(config_file)

    http_server = Thread(target=lambda: start_http_server(config, lock, "0.0.0.0", 8080))
    http_server.start()
    service = Thread(target=lambda: start_reconcile_service(config, lock))
    service.start()

    http_server.join()
    service.join()


def start_reconcile_service(_: Configuration, lock: Lock):
    # The reconcile service is not implemented yet, current logging the lock status.
    while True:
        logging.info("The lock status: %s", lock.locked())
        sleep(60)
