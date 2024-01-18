# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import json
import logging
import platform
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional, Union
from urllib.parse import urlsplit

from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, root_validator
from pydantic.networks import IPvAnyAddress

from firewall import FirewallEntry
from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}

ARCHITECTURES_X86 = {"x86_64"}

CHARM_STATE_PATH = Path("charm_state.json")


@dataclasses.dataclass
class GithubRepo:
    """Represent GitHub repository."""

    owner: str
    repo: str

    def path(self) -> str:
        """Return a string representing the path."""
        return f"{self.owner}/{self.repo}"


@dataclasses.dataclass
class GithubOrg:
    """Represent GitHub organization."""

    org: str
    group: str

    def path(self) -> str:
        """Return a string representing the path."""
        return self.org


GithubPath = Union[GithubOrg, GithubRepo]


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration."""

    cpu: int
    memory: str
    disk: str


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


def _valid_storage_size_str(size: str) -> bool:
    """Validate the storage size string.

    Args:
        size: Storage size string.

    Return:
        Whether the string is valid.
    """
    # Checks whether the string confirms to using the KiB, MiB, GiB, TiB, PiB,
    # EiB suffix for storage size as specified in config.yaml.
    valid_suffixes = ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    valid = any(suffix == size[-3:] for suffix in valid_suffixes)

    valid = valid or size[:-3].isdigit()
    return valid


class CharmConfig(BaseModel):
    """General charm configuration.

    Some charm configurations are grouped into other configuration models.

    Attributes:
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        token: GitHub personal access token for GitHub API.
    """

    path: GithubPath
    token: str
    reconcile_interval: int
    denylist: list[str]
    dockerhub_mirror: str | None

    @classmethod
    def _parse_path(cls, charm: CharmBase) -> GithubPath:
        path_str = charm.config.get("path")
        if not path_str:
            raise CharmConfigInvalidError("Missing path configuration")

        path: GithubPath
        if "/" in path_str:
            paths = path_str.split("/")
            if len(paths) != 2:
                raise CharmConfigInvalidError(f"Invalid path configuration {path_str}")
            owner, repo = paths
            path = GithubRepo(owner=owner, repo=repo)
        else:
            runner_group = charm.config.get("group", "")
            path = GithubOrg(org=path_str, group=runner_group)
        return path

    @classmethod
    def _parse_denylist(cls, charm: CharmBase) -> list[str]:
        denylist_str = charm.config.get("denylist", "")

        entry_list = [entry.strip() for entry in denylist_str.split(",")]
        denylist = [FirewallEntry.decode(entry) for entry in entry_list if entry]
        return denylist

    @classmethod
    def _parse_dockerhub_mirror(cls, charm: CharmBase) -> str | None:
        dockerhub_mirror = charm.config.get("dockerhub_mirror") or None

        dockerhub_mirror_url = urlsplit(dockerhub_mirror)
        if dockerhub_mirror is not None and dockerhub_mirror_url.scheme != "https":
            raise CharmConfigInvalidError(
                (
                    "Only secured registry supported for dockerhub-mirror configuration, the "
                    "scheme should be https"
                )
            )
        return dockerhub_mirror

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "CharmConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current config of the charm.
        """
        path = cls._parse_path(charm)

        token = charm.config.get("token")
        if not token:
            raise CharmConfigInvalidError("Missing token configuration")

        try:
            reconcile_interval = int(charm.config["reconcile-interval"])
        except ValueError as err:
            raise CharmConfigInvalidError("The reconcile-interval config must be int") from err

        denylist = cls._parse_denylist(charm)
        dockerhub_mirror = cls._parse_dockerhub_mirror(charm)

        return cls(
            path=path,
            token=token,
            reconcile_interval=reconcile_interval,
            denylist=denylist,
            dockerhub_mirror=dockerhub_mirror,
        )

    @root_validator
    @classmethod
    def check_fields(cls, values: dict) -> dict:
        """Validate the general charm configuration."""
        reconcile_interval = values.get("reconcile_interval")
        # By property definition, this cannot be None.
        assert reconcile_interval is not None, "Unreachable code"

        if reconcile_interval < 2:
            logger.exception("The virtual-machines configuration must be int")
            raise ValueError(
                "The reconcile_interval configuration needs to be greater or equal to 2"
            )

        return values


class RunnerConfig(BaseModel):
    """Runner configurations.

    Attributes:
        virtual_machines: Number of virtual machine-based runner to spawn.
        runner_storage: Storage to be used as disk for the runner.
    """

    virtual_machines: int
    virtual_machine_resources: VirtualMachineResources
    runner_storage: RunnerStorage

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "RunnerConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current config of the charm.
        """
        try:
            runner_storage = RunnerStorage(charm.config["runner-storage"])
        except ValueError as err:
            raise CharmConfigInvalidError("Invalid runner-storage configuration") from err

        try:
            virtual_machines = int(charm.config["virtual_machines"])
        except ValueError as err:
            raise CharmConfigInvalidError(
                "The virtual-machines configuration must be int"
            ) from err

        try:
            cpu = int(charm.config["vm-cpu"])
        except ValueError as err:
            raise CharmConfigInvalidError("Invalid vm-cpu configuration") from err

        virtual_machine_resources = VirtualMachineResources(
            cpu, charm.config["vm-memory"], charm.config["vm-disk"]
        )

        return cls(
            virtual_machines=virtual_machines,
            virtual_machine_resources=virtual_machine_resources,
            runner_storage=runner_storage,
        )

    @root_validator
    @classmethod
    def check_fields(cls, values: dict) -> dict:
        """Validate the runner configuration."""
        virtual_machines = values.get("virtual_machines")
        resources = values.get("virtual_machine_resources")
        # By property definition, these cannot be None.
        assert virtual_machines is not None, "Unreachable code"
        assert resources is not None, "Unreachable code"

        if virtual_machines < 0:
            raise ValueError(
                "The virtual-machines configuration needs to be greater or equal to 0"
            )

        if resources.cpu < 1:
            raise ValueError("The vm-cpu configuration needs to be greater than 0")
        if _valid_storage_size_str(resources.memory):
            raise ValueError("Invalid vm-memory configuration")
        if _valid_storage_size_str(resources.disk):
            raise ValueError("Invalid vm-disk configuration")

        return values


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
    rsa_fingerprint: str = Field(pattern="^SHA256:.*")
    ed25519_fingerprint: str = Field(pattern="^SHA256:.*")

    @classmethod
    def from_charm(cls, charm: CharmBase) -> Optional["SSHDebugInfo"]:
        """Initialize the SSHDebugInfo from charm relation data.

        Args:
            charm: The charm instance.
        """
        relations = charm.model.relations[DEBUG_SSH_INTEGRATION_NAME]
        if not relations or not (relation := relations[0]).units:
            return None
        target_unit = next(iter(relation.units))
        relation_data = relation.data[target_unit]
        if (
            not (host := relation_data.get("host"))
            or not (port := relation_data.get("port"))
            or not (rsa_fingerprint := relation_data.get("rsa_fingerprint"))
            or not (ed25519_fingerprint := relation_data.get("ed25519_fingerprint"))
        ):
            logger.warning("%s relation data not yet ready.", DEBUG_SSH_INTEGRATION_NAME)
            return None
        return SSHDebugInfo(
            host=host,
            port=port,
            rsa_fingerprint=rsa_fingerprint,
            ed25519_fingerprint=ed25519_fingerprint,
        )


@dataclasses.dataclass(frozen=True)
class State:
    """The charm state.

    Attributes:
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Proxy-related configuration.
        charm_config: Configuration of the juju charm.
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        ssh_debug_info: The SSH debug connection configuration information.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    charm_config: CharmConfig
    runner_config: RunnerConfig
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

        try:
            runner_config = RunnerConfig.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError("Invalid runner configuration") from exc

        if (
            prev_state is not None
            and prev_state["runner_config"]["runner_storage"] != runner_config.runner_storage
        ):
            logger.warning(
                "Storage option changed from %s to %s, blocking the charm",
                prev_state["runner_config"]["runner_storage"],
                runner_config.runner_storage,
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
            ssh_debug_info = SSHDebugInfo.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid SSH debug info: %s.", exc)
            raise CharmConfigInvalidError("Invalid SSH Debug info") from exc

        state = cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            charm_config=charm_config,
            runner_config=runner_config,
            arch=arch,
            ssh_debug_info=ssh_debug_info,
        )

        state_dict = dataclasses.asdict(state)
        # Convert pydantic object to python object serializable by json module.
        state_dict["proxy_config"] = json.loads(state_dict["proxy_config"].json())
        state_dict["charm_config"] = json.loads(state_dict["charm_config"].json())
        json_data = json.dumps(state_dict, ensure_ascii=False)
        CHARM_STATE_PATH.write_text(json_data, encoding="utf-8")

        return state
