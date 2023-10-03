#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The COS integration observer."""
import json
import logging

import ops
from charms.loki_k8s.v0.loki_push_api import (
    LokiPushApiConsumer,
    LokiPushApiEndpointDeparted,
    LokiPushApiEndpointJoined,
)
from ops import EventBase, Relation
from pydantic import AnyHttpUrl, BaseModel

import promtail
from charm_state import State
from event_timer import EventTimer

METRICS_LOGGING_INTEGRATION_NAME = "metrics-logging"

PROMTAIL_HEALTH_CHECK_INTERVAL_MINUTES = 5

logger = logging.getLogger(__name__)


class PromtailBinary(BaseModel):
    """Information about the Promtail binary.

    Attrs:
        url: The URL to download the Promtail binary from.
        zipsha: The SHA256 hash of the Promtail zip file.
        binsha: The SHA256 hash of the Promtail binary.
    """

    url: AnyHttpUrl
    zipsha: str
    binsha: str


class LokiEndpoint(BaseModel):
    """Information about the Loki endpoint.

    Attrs:
        url: The URL of the Loki endpoint.
    """

    url: AnyHttpUrl


class LokiIntegrationData(BaseModel):
    """Represents Loki integration data.

    Attrs:
        endpoints: The Loki endpoints.
        promtail_binaries: The Promtail binaries.
    """

    endpoints: list[LokiEndpoint]
    promtail_binaries: dict[str, PromtailBinary]


class LokiIntegrationDataIncompleteError(Exception):
    """Indicates an error if the Loki integration data is not complete for Promtail startup."""

    def __init__(self, msg: str):
        """Initialize a new instance of the LokiIntegrationDataNotComplete exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class PromtailHealthCheckEvent(EventBase):
    """Event representing a periodic check to ensure Promtail is running."""


class Observer(ops.Object):
    """COS integration observer."""

    def __init__(self, charm: ops.CharmBase, state: State):
        """Initialize the COS observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            state: The charm state.
        """
        super().__init__(charm, "cos-observer")
        self.state = state
        self.charm = charm
        self._event_timer = EventTimer(charm.unit.name)

        self._loki_consumer = LokiPushApiConsumer(
            charm=charm, relation_name=METRICS_LOGGING_INTEGRATION_NAME
        )
        charm.framework.observe(
            self._loki_consumer.on.loki_push_api_endpoint_joined,
            self._on_loki_push_api_endpoint_joined,
        )
        charm.framework.observe(
            self._loki_consumer.on.loki_push_api_endpoint_departed,
            self._on_loki_push_api_endpoint_departed,
        )
        charm.on.define_event("promtail_health", PromtailHealthCheckEvent)

        charm.framework.observe(charm.on.promtail_health, self._on_promtail_health)

    def _retrieve_loki_integration_data(self) -> LokiIntegrationData:
        """Retrieve and validate Loki integration data.

        Returns:
            The validated integration data.
        Raises:
            pydantic.ValidationError: If the integration data is not valid.
        """
        loki_endpoints = []
        for endpoint in self._loki_consumer.loki_endpoints:
            loki_endpoints.append(LokiEndpoint(url=endpoint.get("url")))
        logger.debug("Found following Loki endpoints: %s", loki_endpoints)

        relations: list[Relation] = self.charm.model.relations["metrics-logging"]
        promtail_binaries = {}

        if relations and (relation := relations[0]).app:
            promtail_binaries_json = json.loads(
                relation.data[relation.app].get("promtail_binary_zip_url", "{}")
            )
            promtail_binaries = {
                arch: PromtailBinary(**info) for arch, info in promtail_binaries_json.items()
            }
            logger.debug("Found following promtail binaries: %s", promtail_binaries)

        return LokiIntegrationData(endpoints=loki_endpoints, promtail_binaries=promtail_binaries)

    def _validate_for_start(self, loki_integration_data: LokiIntegrationData) -> None:
        """Validate that the Loki integration data is complete to start Promtail.

        Args:
            loki_integration_data: The Loki integration data to validate.

        Raises:
            LokiIntegrationDataNotComplete: If the integration data is not complete.
        """
        if not loki_integration_data.endpoints:
            raise LokiIntegrationDataIncompleteError("No Loki endpoint found.")
        if not loki_integration_data.promtail_binaries.get("amd64"):
            raise LokiIntegrationDataIncompleteError(
                "No Promtail binary information for amd64 architecture found."
            )

    def metrics_logging_available(self) -> bool:
        """Check that the metrics logging integration is set up correctly.

        Returns:
            True if the integration is established, False otherwise.
        """
        return bool(self._retrieve_loki_integration_data().endpoints)

    def _start_promtail(self, loki_integration_data: LokiIntegrationData) -> None:
        """Start Promtail.

        Args:
            loki_integration_data: The Loki integration data.
        """
        promtail_binary = loki_integration_data.promtail_binaries["amd64"]
        dl_info = promtail.PromtailDownloadInfo(
            url=promtail_binary.url,
            zip_sha256=promtail_binary.zipsha,
            bin_sha256=promtail_binary.binsha,
        )

        config = promtail.Config(
            loki_integration_data.endpoints[0].url, self.state.proxy_config, dl_info
        )
        logger.info("Starting Promtail")
        promtail.start(config)

    def _on_loki_push_api_endpoint_joined(
        self, event: LokiPushApiEndpointJoined  # pylint: disable=unused-argument
    ) -> None:
        """Handle the LokiPushApiEndpointJoined event.

        Configures Promtail to send logs to the Loki endpoint and enables health check, but only
        if the Loki integration data is complete for Promtail startup.

        Args:
            event: The event object containing the Loki endpoint.
        """
        loki_integration_data = self._retrieve_loki_integration_data()
        try:
            self._validate_for_start(loki_integration_data)
        except LokiIntegrationDataIncompleteError as exc:
            logger.info("Loki integration data not complete: %s Will not start Promtail", exc.msg)
            return

        self._start_promtail(loki_integration_data)
        self._event_timer.ensure_event_timer(
            "promtail-health", PROMTAIL_HEALTH_CHECK_INTERVAL_MINUTES
        )

    def _on_loki_push_api_endpoint_departed(
        self, event: LokiPushApiEndpointDeparted  # pylint: disable=unused-argument
    ) -> None:
        """Handle the LokiPushApiEndpointDeparted event.

        Stops Promtail and disables event timer for health check.

        Args:
            event: The event object.
        """
        loki_integration_data = self._retrieve_loki_integration_data()
        if not loki_integration_data.endpoints:
            logger.info("No Loki endpoints found. Stopping Promtail...")
            promtail.stop()
            self._event_timer.disable_event_timer("promtail-health")
        else:
            try:
                self._validate_for_start(loki_integration_data)
            except LokiIntegrationDataIncompleteError as exc:
                logger.warning(
                    "Loki integration data not complete: %s . Will not start Promtail", exc.msg
                )
                return
            self._start_promtail(loki_integration_data)

    def _on_promtail_health(
        self, event: PromtailHealthCheckEvent  # pylint: disable=unused-argument
    ) -> None:
        """Handle the PromtailHealthCheckEvent event.

        Restarts Promtail if it is not running.

        Args:
            event: The event object
        """
        if not promtail.is_running():
            logger.error("Promtail is not running, restarting")
            promtail.restart()
