#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging
from typing import Optional

from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel, ValidationError, root_validator

from utilities import get_env_var

logger = logging.getLogger(__name__)

COS_AGENT_INTEGRATION_NAME = "cos-agent"


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


class ProxyConfig(BaseModel):
    """Proxy configuration.

    Attributes:
        http_proxy: HTTP proxy address.
        https_proxy: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
        use_aproxy: Whether aproxy should be used.
    """

    http_proxy: Optional[AnyHttpUrl]
    https_proxy: Optional[AnyHttpUrl]
    no_proxy: Optional[str]
    use_aproxy: bool

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "ProxyConfig":
        """Initialize the proxy config from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current proxy config of the charm.
        """
        use_aproxy = bool(charm.config.get("experimental-use-aproxy"))
        http_proxy = get_env_var("JUJU_CHARM_HTTP_PROXY") or None
        https_proxy = get_env_var("JUJU_CHARM_HTTPS_PROXY") or None
        no_proxy = get_env_var("JUJU_CHARM_NO_PROXY") or None

        return cls(
            http_proxy=http_proxy,
            https_proxy=https_proxy,
            no_proxy=no_proxy,
            use_aproxy=use_aproxy,
        )

    @property
    def aproxy_address(self) -> Optional[str]:
        """Return the aproxy address."""
        if self.use_aproxy:
            proxy_address = self.http_proxy or self.https_proxy
            # assert is only used to make mypy happy
            assert proxy_address is not None  # nosec for [B101:assert_used]
            aproxy_address = f"{proxy_address.host}:{proxy_address.port}"
        else:
            aproxy_address = None
        return aproxy_address

    @root_validator
    @classmethod
    def check_fields(cls, values: dict) -> dict:
        """Validate the proxy configuration."""
        if values.get("use_aproxy") and not (
            values.get("http_proxy") or values.get("https_proxy")
        ):
            raise ValueError("aproxy requires http_proxy or https_proxy to be set")

        return values


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Whether aproxy should be used.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current state of the charm.
        """
        try:
            proxy_config = ProxyConfig.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid proxy config: %s", exc)
            raise CharmConfigInvalidError("Invalid proxy configuration") from exc

        return cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
        )
