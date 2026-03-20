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
from types import FrameType
from typing import TextIO

import click

from github_runner_manager.configuration import ApplicationConfiguration
from github_runner_manager.http_server import FlaskArgs, start_http_server
from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    build_pressure_reconciler,
    build_runner_manager,
)
from github_runner_manager.reconcile_service import start_reconcile_service
from github_runner_manager.thread_manager import ThreadManager

version = importlib.metadata.version("github-runner-manager")


def handle_shutdown(
    signum: int,
    _frame: FrameType | None,
    pressure_reconciler: PressureReconciler,
    thread_manager: ThreadManager,
) -> None:  # pragma: no cover
    """Stop reconciler threads on shutdown signals.

    Signals the reconciler loops to stop, waits for all threads to finish
    their current operation, then exits the process.

    Args:
        signum: Received POSIX signal number.
        _frame: Current stack frame when the signal was received.
        pressure_reconciler: The reconciler instance to stop.
        thread_manager: The thread manager whose threads to join before exiting.

    Raises:
        SystemExit: Always raised after graceful shutdown to terminate the process.
    """
    logging.info("Received signal %s; stopping pressure reconciler", signum)
    pressure_reconciler.stop()
    for thread in thread_manager.threads:
        thread.join(timeout=60)
    raise SystemExit(0)


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
    required=False,
    help="The PYTHONPATH to access the github-runner-manager library.",
)
# The entry point for the CLI will be tested with integration test.
def main(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    config_file: TextIO,
    host: str,
    port: int,
    debug: bool,
    python_path: str | None,
    log_level: str,
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        python_path: PYTHONPATH to access the github-runner-manager library.
        log_level: The log level.
    """
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Starting GitHub runner manager service version: %s", version)
    config = ApplicationConfiguration.from_yaml_file(StringIO(config_file.read()))
    lock = Lock()

    combinations = config.non_reactive_configuration.combinations
    runner_manager = build_runner_manager(config, combinations[0])

    thread_manager = ThreadManager()
    http_server_args = FlaskArgs(host=host, port=port, debug=debug)
    thread_manager.add_thread(
        target=partial(start_http_server, runner_manager, lock, http_server_args),
        daemon=True,
    )

    if config.planner_url and config.planner_token:
        pressure_reconciler = build_pressure_reconciler(config, lock)
        shutdown = partial(
            handle_shutdown,
            pressure_reconciler=pressure_reconciler,
            thread_manager=thread_manager,
        )
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        thread_manager.add_thread(target=pressure_reconciler.start_create_loop, daemon=True)
        thread_manager.add_thread(target=pressure_reconciler.start_reconcile_loop, daemon=True)
    # Legacy mode is still supported for deployments without planner config.
    else:
        thread_manager.add_thread(
            target=partial(start_reconcile_service, config, python_path, lock),
            daemon=True,
        )

    thread_manager.start()
    thread_manager.raise_on_error()
