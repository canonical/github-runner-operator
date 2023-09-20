#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions for operating Promtail."""
from dataclasses import dataclass
from typing import Optional

from charm_state import ProxyConfig


@dataclass
class Config:
    """Configuration options for Promtail."""

    loki_endpoint: str
    """The Loki endpoint to send logs to."""
    proxies: Optional[ProxyConfig]
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
