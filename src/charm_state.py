#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging
import platform
from enum import Enum
from typing import Optional

from ops import CharmBase, Unit
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, root_validator
from pydantic.networks import IPvAnyAddress

from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}

ARCHITECTURES_X86 = {"x86_64"}


class ARCH(str, Enum):
    """Supported system architectures."""

    ARM64 = "arm64"
    X64 = "x64"


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


class UnsupportedArchitectureError(Exception):
    """Raised when given machine charm architecture is unsupported.

    Attributes:
        arch: The current machine architecture.
    """

    def __init__(self, arch: str) -> None:
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            arch: The current machine architecture.
        """
        self.arch = arch


def _get_supported_arch() -> ARCH:
    """Get current machine architecture.

    Raises:
        UnsupportedArchitectureError: if the current architecture is unsupported.

    Returns:
        Arch: Current machine architecture.
    """
    arch = platform.machine()
    match arch:
        case arch if arch in ARCHITECTURES_ARM64:
            return ARCH.ARM64
        case arch if arch in ARCHITECTURES_X86:
            return ARCH.X64
        case _:
            raise UnsupportedArchitectureError(arch=arch)


SSH_DEBUG_RELATION = "ssh-debug"


class SSHDebugInfo(BaseModel):
    """SSH connection information for debug workflow.

    Attributes:
        host: The SSH relay server host IP address inside the VPN.
        port: The SSH relay server port.
        rsa_fingerprint: The host SSH server public RSA key fingerprint.
        ed25519_fingerprint: The host SSH server public ed25519 key fingerprint.
    """

    host: IPvAnyAddress
    port: int = Field(0, gt=0, le=65535)
    rsa_fingerprint: str
    ed25519_fingerprint: str

    @staticmethod
    def _circular_ring_hash(
        unit_num: int, num_planned_units: int, related_units: set[Unit]
    ) -> Unit:
        """Get a matched unit through circular ring hash distribution method.

        Args:
            cur_unit_num: The current unit number (nth unit)

        """
        # if unit has been deleted and scaled, the unit number will be greater than number of total
        # units available.
        adjusted_unit_num = (
            unit_num if unit_num < num_planned_units else unit_num - num_planned_units
        )
        total_related_units = len(related_units)
        return list(related_units)[adjusted_unit_num % total_related_units]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "SSHDebugInfo" | None:
        """Initialize the SSHDebugInfo from charm relation data.

        Args:
            charm: The charm instance.
        """
        relations = charm.model.relations[SSH_DEBUG_RELATION]
        if not relations:
            return
        relation = relations[0]
        num_units = charm.app.planned_units()
        unit_num = int(charm.unit.name.split("/")[-1])
        target_unit = cls._circular_ring_hash(unit_num, num_units, relation.units)
        relation_data = relation.data[target_unit]
        return SSHDebugInfo(
            host=relation_data.get("host"),
            port=relation_data.get("port"),
            rsa_fingerprint=relation_data.get("rsa_fingerprint"),
            ed25519_fingerprint=relation_data.get("ed25519_fingerprint"),
        )


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Whether aproxy should be used.
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        ssh_debug_info: The SSH debug connection configuration information.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    arch: ARCH
    ssh_debug_info: Optional[SSHDebugInfo]

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

        try:
            arch = _get_supported_arch()
        except UnsupportedArchitectureError as exc:
            logger.error("Unsupported architecture: %s", exc.arch)
            raise CharmConfigInvalidError(f"Unsupported architecture {exc.arch}") from exc

        try:
            ssh_debug_info = SSHDebugInfo.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid SSH debug info: %s.", exc)
            raise CharmConfigInvalidError("Invalid SSH Debug info") from exc

        return cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            arch=arch,
            ssh_info=ssh_debug_info,
        )
