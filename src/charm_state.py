#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging

from ops import CharmBase

logger = logging.getLogger(__name__)

COS_AGENT_INTEGRATION_NAME = "cos-agent"


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        proxy_config: Proxy configuration.
        _charm: The charm instance.
    """

    is_metrics_logging_available: bool

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Returns:
            Current state of the charm.
        """
        return cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME])
        )
