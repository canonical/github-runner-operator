#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions for operating Promtail."""


def install() -> None:
    """Install Promtail."""


def config(loki_endpoint: str) -> None:
    """Configure Promtail.

    Args:
        loki_endpoint: The Loki endpoint to send logs to.
    """


def start() -> None:
    """Start Promtail."""


def stop() -> None:
    """Stop Promtail."""
