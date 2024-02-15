# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import json
import logging
import platform
from enum import Enum
from pathlib import Path
from typing import Optional

from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, root_validator
from pydantic.networks import IPvAnyAddress

from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}

ARCHITECTURES_X86 = {"x86_64"}

CHARM_STATE_PATH = Path("charm_state.json")


class ARCH(str, Enum):
    """Supported system architectures."""

    ARM64 = "arm64"
    X64 = "x64"


COS_AGENT_INTEGRATION_NAME = "cos-agent"
DEBUG_SSH_INTEGRATION_NAME = "debug-ssh"


class RunnerStorage(str, Enum):
    """Supported storage as runner disk."""

    JUJU_STORAGE = "juju-storage"
    MEMORY = "memory"


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


class CharmConfig(BaseModel):
    """Charm configuration.

    Attributes:
        runner_storage: Storage to be used as disk for the runner.
    """

    runner_storage: RunnerStorage

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "CharmConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current config of the charm.
        """
        try:
            runner_storage = RunnerStorage(charm.config.get("runner-storage"))
        except ValueError as err:
            logger.exception("Invalid runner-storage configuration")
            raise CharmConfigInvalidError("Invalid runner-storage configuration") from err

        return cls(runner_storage=runner_storage)


class ProxyConfig(BaseModel):
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
        use_aproxy: Whether aproxy should be used for the runners.
    """

    http: Optional[AnyHttpUrl]
    https: Optional[AnyHttpUrl]
    no_proxy: Optional[str]
    use_aproxy: bool = False

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

        # there's no need for no_proxy if there's no http_proxy or https_proxy
        if not (https_proxy or http_proxy) and no_proxy:
            no_proxy = None

        return cls(
            http=http_proxy,
            https=https_proxy,
            no_proxy=no_proxy,
            use_aproxy=use_aproxy,
        )

    @property
    def aproxy_address(self) -> Optional[str]:
        """Return the aproxy address."""
        if self.use_aproxy:
            proxy_address = self.http or self.https
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
            values.get("http") or values.get("https")
        ):
            raise ValueError("aproxy requires http or https to be set")

        return values

    def __bool__(self):
        """Return whether we have a proxy config."""
        return bool(self.http or self.https)

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic model configuration.

        Attributes:
            allow_mutation: Whether the model is mutable.
        """

        allow_mutation = False


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


class SSHDebugConnection(BaseModel):
    """SSH connection information for debug workflow.

    Attributes:
        host: The SSH relay server host IP address inside the VPN.
        port: The SSH relay server port.
        rsa_fingerprint: The host SSH server public RSA key fingerprint.
        ed25519_fingerprint: The host SSH server public ed25519 key fingerprint.
    """

    host: IPvAnyAddress
    port: int = Field(0, gt=0, le=65535)
    rsa_fingerprint: str = Field(pattern="^SHA256:.*")
    ed25519_fingerprint: str = Field(pattern="^SHA256:.*")

    @classmethod
    def from_charm(cls, charm: CharmBase) -> list["SSHDebugConnection"]:
        """Initialize the SSHDebugInfo from charm relation data.

        Args:
            charm: The charm instance.
        """
        ssh_debug_connections: list[SSHDebugConnection] = []
        relations = charm.model.relations[DEBUG_SSH_INTEGRATION_NAME]
        if not relations or not (relation := relations[0]).units:
            return ssh_debug_connections
        for unit in relation.units:
            relation_data = relation.data[unit]
            if (
                not (host := relation_data.get("host"))
                or not (port := relation_data.get("port"))
                or not (rsa_fingerprint := relation_data.get("rsa_fingerprint"))
                or not (ed25519_fingerprint := relation_data.get("ed25519_fingerprint"))
            ):
                logger.warning(
                    "%s relation data for %s not yet ready.", DEBUG_SSH_INTEGRATION_NAME, unit.name
                )
                continue
            ssh_debug_connections.append(
                SSHDebugConnection(
                    host=host,
                    port=port,
                    rsa_fingerprint=rsa_fingerprint,
                    ed25519_fingerprint=ed25519_fingerprint,
                )
            )
        return ssh_debug_connections


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Proxy-related configuration.
        charm_config: Configuration of the juju charm.
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        ssh_debug_connections: SSH debug connections configuration information.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    charm_config: CharmConfig
    arch: ARCH
    ssh_debug_connections: list[SSHDebugConnection]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "State":
        """Initialize the state from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current state of the charm.
        """
        prev_state = None
        if CHARM_STATE_PATH.exists():
            json_data = CHARM_STATE_PATH.read_text(encoding="utf-8")
            prev_state = json.loads(json_data)
            logger.info("Previous charm state: %s", prev_state)

        try:
            proxy_config = ProxyConfig.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid proxy config: %s", exc)
            raise CharmConfigInvalidError("Invalid proxy configuration") from exc

        try:
            charm_config = CharmConfig.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError("Invalid charm configuration") from exc

        if (
            prev_state is not None
            and prev_state["charm_config"]["runner_storage"] != charm_config.runner_storage
        ):
            logger.warning(
                "Storage option changed from %s to %s, blocking the charm",
                prev_state["charm_config"]["runner_storage"],
                charm_config.runner_storage,
            )
            raise CharmConfigInvalidError(
                "runner-storage config cannot be changed after deployment, redeploy if needed"
            )
        try:
            arch = _get_supported_arch()
        except UnsupportedArchitectureError as exc:
            logger.error("Unsupported architecture: %s", exc.arch)
            raise CharmConfigInvalidError(f"Unsupported architecture {exc.arch}") from exc

        try:
            ssh_debug_connections = SSHDebugConnection.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid SSH debug info: %s.", exc)
            raise CharmConfigInvalidError("Invalid SSH Debug info") from exc

        state = cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            charm_config=charm_config,
            arch=arch,
            ssh_debug_connections=ssh_debug_connections,
        )

        state_dict = dataclasses.asdict(state)
        # Convert pydantic object to python object serializable by json module.
        state_dict["proxy_config"] = json.loads(state_dict["proxy_config"].json())
        state_dict["charm_config"] = json.loads(state_dict["charm_config"].json())
        state_dict["ssh_debug_connections"] = [
            debug_info.json() for debug_info in state_dict["ssh_debug_connections"]
        ]
        json_data = json.dumps(state_dict, ensure_ascii=False)
        CHARM_STATE_PATH.write_text(json_data, encoding="utf-8")

        return state
