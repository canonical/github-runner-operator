#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging
import re
from typing import Optional

from ops import CharmBase

logger = logging.getLogger(__name__)

COS_AGENT_INTEGRATION_NAME = "cos-agent"
HOSTNAME_PORT_PATTERN = re.compile(r"^[\w\-.]+:\d+$")


class CharmConfigInvalidError(Exception):
    """Raised when charm config is invalid.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        aproxy_address: The socket address of the proxy to configure aproxy with.
    """

    is_metrics_logging_available: bool
    aproxy_address: Optional[str]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current state of the charm.
        """
        if aproxy_address := charm.config.get("aproxy-address"):
            if not HOSTNAME_PORT_PATTERN.match(aproxy_address):
                raise CharmConfigInvalidError(
                    f"aproxy-address must be a valid socket address, got {aproxy_address}"
                )
        else:
            aproxy_address = None
        return cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            aproxy_address=aproxy_address,
        )
