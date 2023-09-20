#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions for operating Promtail."""
from dataclasses import dataclass
from typing import Optional

from metrics import Event
from runner_type import ProxySetting


@dataclass
class Config:
    """Configuration options for Promtail."""

    loki_endpoint: str
    """The Loki endpoint to send logs to."""
    proxies: Optional[ProxySetting]
    """Proxy settings."""


def start(config: Config) -> None:
    """Start Promtail.

    If Promtail has not already been installed, it will be installed
    and configured to send logs to Loki.
    If Promtail is already running, it will be reconfigured and restarted.

    Args:
        config: The configuration for Promtail.
    """


def stop() -> None:
    """Stop Promtail."""


def setup_logging() -> None:
    """Set up metric logging for the application.

    Creates the logs directory if it does not exist.
    Setups logrotate to rotate the logs.
    """


def log_event(event: Event) -> None:
    """Log a metric event to be picked up by Promtail.

    Args:
        event: The metric event to log.
    """