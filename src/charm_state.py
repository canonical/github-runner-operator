#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging

from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel

logger = logging.getLogger(__name__)

COS_AGENT_INTEGRATION_NAME = "cos-agent"


class LokiEndpoint(BaseModel):
    """Information about the Loki endpoint.

    Attrs:
        url: The URL of the Loki endpoint.
    """

    url: AnyHttpUrl


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attrs:
        proxy_config: Proxy configuration.
        _charm: The charm instance.
    """

    _charm: CharmBase

    @property
    def is_metrics_logging_available(self) -> bool:
        """Return whether metric logging is available.

        Returns:
            True if metric logging is available, False otherwise.
        """
        return bool(self._charm.model.relations[COS_AGENT_INTEGRATION_NAME])

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Returns:
            Current state of the charm.
        """
        return cls(_charm=charm)
