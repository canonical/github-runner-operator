#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
from typing import Optional

from pydantic import BaseModel, HttpUrl

from utilities import get_env_var


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
    def from_env(cls) -> Optional["ProxyConfig"]:
        """Instantiate ProxyConfig from juju charm environment.

        Returns:
            ProxyConfig if proxy configuration is provided, None otherwise.
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


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attrs:
        proxy_config: Proxy configuration.
    """

    proxy_config: Optional[ProxyConfig]

    @classmethod
    def from_charm(cls) -> "State":
        """Initialize the state from charm.

        Returns:
            Current state of the charm.
        """
        proxy_config = ProxyConfig.from_env()
        return cls(proxy_config=proxy_config)
