#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
from typing import Optional

from ops import CharmBase
from pydantic import BaseModel, HttpUrl


class ProxyConfig(BaseModel):
    """Configuration for proxy.

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


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attrs:
        proxy_config: Proxy configuration.
    """

    proxy_config: Optional[ProxyConfig]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Args:
            charm: The charm root GithubRunnerCharm.

        Returns:
            Current state of the charm.
        """
