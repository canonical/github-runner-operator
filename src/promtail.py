#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions for operating Promtail."""


def install_promtail() -> None:
    """Install Promtail."""


def config_promtail(loki_endpoint: str) -> None:
    """Configure Promtail.

    Args:
        loki_endpoint: The Loki endpoint to send logs to.
    """


def start_promtail() -> None:
    """Start Promtail."""


def stop_promtail():
    """Stop Promtail."""
