#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging
from typing import Optional

from charms.loki_k8s.v0.loki_push_api import LokiPushApiConsumer
from pydantic import AnyHttpUrl, BaseModel, HttpUrl

from utilities import get_env_var

logger = logging.getLogger(__name__)


class ProxyConfig(BaseModel):
    """Represent HTTP-related proxy settings.

    Attributes:
        http_proxy: The http proxy URL.
        https_proxy: The https proxy URL.
        no_proxy: Comma separated list of hostnames to bypass proxy.
    """

    http_proxy: Optional[HttpUrl]
    https_proxy: Optional[HttpUrl]
    no_proxy: Optional[str]

    @classmethod
    def from_env(cls) -> "ProxyConfig":
        """Instantiate ProxyConfig from juju charm environment.

        Returns:
            The proxy configuration.
        """
        http = https = no_proxy = None
        if http_proxy := get_env_var("JUJU_CHARM_HTTP_PROXY"):
            http = http_proxy
        if https_proxy := get_env_var("JUJU_CHARM_HTTPS_PROXY"):
            https = https_proxy
        # there's no need for no_proxy if there's no http_proxy or https_proxy
        no_proxy_env = get_env_var("JUJU_CHARM_NO_PROXY")
        if (http or https) and no_proxy_env:
            no_proxy = no_proxy_env
        return cls(http_proxy=http, https_proxy=https, no_proxy=no_proxy)


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
        loki_push_api_consumer:
            The consumer which provides the Loki Endpoints from integration data.
    """

    proxy_config: ProxyConfig
    _loki_consumer: LokiPushApiConsumer

    @property
    def is_metrics_logging_available(self) -> bool:
        """Return whether metric logging is available.

        Returns:
            True if metric logging is available, False otherwise.
        """
        return bool(self._loki_consumer.loki_endpoints)

    @property
    def loki_endpoint(self) -> Optional[LokiEndpoint]:
        """Return the Loki endpoint.

        Returns:
            The Loki endpoint if available, None otherwise.
        """
        loki_endpoints = []
        for endpoint in self._loki_consumer.loki_endpoints:
            loki_endpoints.append(LokiEndpoint(url=endpoint.get("url")))
        logger.debug("Found following Loki endpoints: %s", loki_endpoints)
        return loki_endpoints[0] if loki_endpoints else None

    @classmethod
    def from_charm(cls, loki_consumer: LokiPushApiConsumer) -> "State":
        """Initialize the state from charm.

        Returns:
            Current state of the charm.
        """
        proxy_config = ProxyConfig.from_env()
        return cls(proxy_config=proxy_config, _loki_consumer=loki_consumer)
