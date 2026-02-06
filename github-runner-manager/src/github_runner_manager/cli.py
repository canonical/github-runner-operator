# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import getpass
import grp
import importlib.metadata
import logging
import os
import signal
import sys
from functools import partial
from io import StringIO
from threading import Lock
from types import FrameType
from typing import TextIO

import click

from github_runner_manager.configuration import ApplicationConfiguration, UserInfo
from github_runner_manager.http_server import FlaskArgs, start_http_server
from github_runner_manager.manager.pressure_reconciler import (
    PressureReconciler,
    PressureReconcilerConfig,
)
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
)
from github_runner_manager.planner_client import PlannerClient, PlannerConfiguration
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.thread_manager import ThreadManager

version = importlib.metadata.version("github-runner-manager")


def handle_shutdown(
    signum: int, _frame: FrameType | None, pressure_reconciler: PressureReconciler
) -> None:  # pragma: no cover
    """Stop reconciler threads on shutdown signals.

    Args:
        signum: Received POSIX signal number.
        _frame: Current stack frame when the signal was received.
        pressure_reconciler: The reconciler instance to stop.
    """
    logging.info("Received signal %s; stopping pressure reconciler", signum)
    pressure_reconciler.stop()


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
# The entry point for the CLI will be tested with integration test.
def main(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    config_file: TextIO,
    host: str,
    port: int,
    debug: bool,
    log_level: str,
) -> None:  # pragma: no cover
    """Start the reconcile service.

    Args:
        config_file: The configuration file.
        host: The hostname to listen on for the HTTP server
        port: The port to listen on the HTTP server.
        debug: Whether to start the application in debug mode.
        log_level: The log level.
    """
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Starting GitHub runner manager service version: %s", version)
    config = ApplicationConfiguration.from_yaml_file(StringIO(config_file.read()))

    thread_manager = ThreadManager()
    thread_manager.add_thread(
        target=partial(
            start_http_server,
            config,
            Lock(),
            FlaskArgs(host=host, port=port, debug=debug),
        ),
        daemon=True,
    )

    pressure_reconciler = PressureReconciler(
        manager=RunnerManager(
            manager_name=config.name,
            platform_provider=GitHubRunnerPlatform.build(
                prefix=config.openstack_configuration.vm_prefix,
                github_configuration=config.github_config,
            ),
            cloud_runner_manager=OpenStackRunnerManager(
                config=OpenStackRunnerManagerConfig(
                    allow_external_contributor=config.allow_external_contributor,
                    prefix=config.openstack_configuration.vm_prefix,
                    credentials=config.openstack_configuration.credentials,
                    server_config=(
                        None
                        if not config.non_reactive_configuration.combinations
                        else OpenStackServerConfig(
                            image=config.non_reactive_configuration.combinations[0].image.name,
                            flavor=config.non_reactive_configuration.combinations[0].flavor.name,
                            network=config.openstack_configuration.network,
                        )
                    ),
                    service_config=config.service_config,
                ),
                user=UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name),
            ),
            labels=(
                list(config.extra_labels)
                + (
                    []
                    if not config.non_reactive_configuration.combinations
                    else (
                        config.non_reactive_configuration.combinations[0].image.labels
                        + config.non_reactive_configuration.combinations[0].flavor.labels
                    )
                )
            ),
        ),
        planner_client=PlannerClient(
            PlannerConfiguration(base_url=config.planner_url, token=config.planner_token)
        ),
        config=PressureReconcilerConfig(
            flavor_name=(
                config.non_reactive_configuration.combinations[0].flavor.name
                if config.non_reactive_configuration.combinations
                else ""
            )
        ),
    )
    signal.signal(
        signal.SIGTERM, partial(handle_shutdown, pressure_reconciler=pressure_reconciler)
    )
    signal.signal(signal.SIGINT, partial(handle_shutdown, pressure_reconciler=pressure_reconciler))
    thread_manager.add_thread(target=pressure_reconciler.start_create_loop, daemon=True)
    thread_manager.add_thread(target=pressure_reconciler.start_delete_loop, daemon=True)

    thread_manager.start()
    thread_manager.raise_on_error()
