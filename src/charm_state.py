# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import json
import logging
import platform
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel, ValidationError, root_validator

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


class RunnerStorage(str, Enum):
    """Supported storage as runner disk."""

    JUJU_STORAGE = "juju-storage"
    MEMORY = "memory"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        raise ValueError(
            f"{value} is not a valid runner storage ({list(cls.__members__.values())})"
        )


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
        runner_storage: Storage to used as disk for the runner.
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
            raise CharmConfigInvalidError(str(err)) from err

        return cls(runner_storage=runner_storage)


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


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Whether aproxy should be used.
        storage_config:
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    charm_config: CharmConfig
    arch: ARCH

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
            with open(CHARM_STATE_PATH, mode="r", encoding="utf-8") as state_file:
                prev_state = json.load(state_file)
                logger.info(prev_state)

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

        state = cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            charm_config=charm_config,
            arch=arch,
        )

        with open(CHARM_STATE_PATH, mode="w", encoding="utf-8") as state_file:
            state_dict = dataclasses.asdict(state)
            # Convert pydantic object to python object serializable by json module.
            state_dict["proxy_config"] = json.loads(state_dict["proxy_config"].json())
            state_dict["charm_config"] = json.loads(state_dict["charm_config"].json())
            json.dump(state_dict, state_file, ensure_ascii=False)

        return state
