# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

import itertools
import logging
import logging.config
from typing import TextIO

import click

from cli_config import Configuration

_LOG_LEVELS = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR)
LOG_LEVELS = tuple(
    str(level)
    for level in itertools.chain(
        _LOG_LEVELS,
        (logging.getLevelName(level) for level in _LOG_LEVELS),
        (logging.getLevelName(level).lower() for level in _LOG_LEVELS),
    )
)


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
    _ = Configuration.from_yaml_file(config_file)
    raise NotImplementedError()
