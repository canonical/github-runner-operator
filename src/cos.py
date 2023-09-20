#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The COS integration observer."""

import ops

from charm_state import State
from lib.charms.loki_k8s.v0.loki_push_api import (
    LokiPushApiEndpointDeparted,
    LokiPushApiEndpointJoined,
)


class Observer(ops.Object):
    """COS integration observer."""

    def __init__(self, charm: ops.CharmBase, state: State):
        """Initialize the COS observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            state: The charm state.
        """

    def _on_loki_push_api_endpoint_joined(self, event: LokiPushApiEndpointJoined) -> None:
        """Handle the LokiPushApiEndpointJoined event.

        Configures Promtail to send logs to the Loki endpoint.

        Args:
            event: The event object containing the Loki endpoint.
        """

    def _on_loki_push_api_endpoint_departed(self, event: LokiPushApiEndpointDeparted) -> None:
        """Handle the LokiPushApiEndpointDeparted event.

        Stops Promtail.

        Args:
            event: The event object.
        """
