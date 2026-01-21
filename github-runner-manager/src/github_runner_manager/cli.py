# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import importlib.metadata
import logging
import signal
import sys
from functools import partial
from io import StringIO
from threading import Lock
from typing import TextIO

import click

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.http_server import FlaskArgs, start_http_server
from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    PressureReconcilerConfig,
)
from github_runner_manager.planner_client import PlannerClient, PlannerConfiguration
from github_runner_manager.reconcile_service import get_runner_scaler
from github_runner_manager.thread_manager import ThreadManager

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
    """
    python_path_config = python_path if python_path else None
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Starting GitHub runner manager service version: %s", version)

    lock = Lock()
    config_str = config_file.read()
    config = ApplicationConfiguration.from_yaml_file(StringIO(config_str))

    thread_manager = ThreadManager()
    http_server_args = FlaskArgs(host=host, port=port, debug=debug)
    thread_manager.add_thread(
        target=partial(start_http_server, config, lock, http_server_args), daemon=True
    )

    combinations = config.non_reactive_configuration.combinations
    flavor_name = combinations[0].flavor.name
    planner_client = PlannerClient(
        PlannerConfiguration(base_url=config.planner_url, token=config.planner_token)
    )
    runner_scaler = get_runner_scaler(config, python_path=python_path_config)
    pressure_reconciler = PressureReconciler(
        manager=runner_scaler._manager,  # type: ignore[attr-defined]
        planner_client=planner_client,
        config=PressureReconcilerConfig(flavor_name=flavor_name),
    )

    def _handle_shutdown(signum: int, _frame) -> None:  # pragma: no cover
        logging.info("Received signal %s; stopping pressure reconciler", signum)
        pressure_reconciler.stop()

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    thread_manager.add_thread(target=pressure_reconciler.start_create_loop, daemon=True)
    thread_manager.add_thread(target=pressure_reconciler.start_delete_loop, daemon=True)

    thread_manager.start()
    thread_manager.raise_on_error()
