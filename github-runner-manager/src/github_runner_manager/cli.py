# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CLI entrypoint for github-runner-manager application."""

from typing import TextIO

import click
from cli_config import Configuration


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
