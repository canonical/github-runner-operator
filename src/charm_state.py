# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import json
import logging
import platform
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional, cast
from urllib.parse import urlsplit

import yaml
from ops import CharmBase
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, root_validator
from pydantic.networks import IPvAnyAddress

from errors import OpenStackInvalidConfigError
from firewall import FirewallEntry
from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}

ARCHITECTURES_X86 = {"x86_64"}

CHARM_STATE_PATH = Path("charm_state.json")


StorageSize = str
"""Representation of storage size with KiB, MiB, GiB, TiB, PiB, EiB as unit."""


@dataclasses.dataclass
class GithubRepo:
    """Represent GitHub repository.

    Attributes:
        owner: Owner of the GitHub repository.
        repo: Name of the GitHub repository.
    """

    owner: str
    repo: str

    def path(self) -> str:
        """Return a string representing the path.

        Returns:
            Path to the GitHub entity.
        """
        return f"{self.owner}/{self.repo}"


@dataclasses.dataclass
class GithubOrg:
    """Represent GitHub organization.

    Attributes:
        org: Name of the GitHub organization.
        group: Runner group to spawn the runners in.
    """

    org: str
    group: str

    def path(self) -> str:
        """Return a string representing the path.

        Returns:
            Path to the GitHub entity.
        """
        return self.org


GithubPath = GithubOrg | GithubRepo


def parse_github_path(path_str: str, runner_group: str) -> GithubPath:
    """Parse GitHub path.

    Args:
        path_str: GitHub path in string format.
        runner_group: Runner group name for GitHub organization. If the path is
            a repository this argument is ignored.
    Returns:
        GithubPath object representing the GitHub repository, or the GitHub
        organization with runner group information.
    """
    if "/" in path_str:
        paths = path_str.split("/")
        if len(paths) != 2:
            raise CharmConfigInvalidError(f"Invalid path configuration {path_str}")
        owner, repo = paths
        return GithubRepo(owner=owner, repo=repo)
    return GithubOrg(org=path_str, group=runner_group)


class VirtualMachineResources(NamedTuple):
    """Virtual machine resource configuration.

    Attributes:
        cpu: Number of vCPU for the virtual machine.
        memory: Amount of memory for the virtual machine.
        disk: Amount of disk for the virtual machine.
    """

    cpu: int
    memory: StorageSize
    disk: StorageSize


class Arch(str, Enum):
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
    valid_suffixes = {"KiB", "MiB", "GiB", "TiB", "PiB", "EiB"}
    return size[-3:] in valid_suffixes and size[:-3].isdigit()


OPENSTACK_CLOUDS_YAML_CONFIG_NAME = "experimental-openstack-clouds-yaml"
CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")


def _validate_openstack_cloud_config(cloud_config: dict) -> None:
    """Validate the format of the cloud configuration.

    Args:
        cloud_config: The configuration in clouds.yaml format to validate.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    # dict of format: {clouds: <cloud-name>: <cloud-config>}
    try:
        clouds = list(cloud_config["clouds"].keys())
    except KeyError as exc:
        raise OpenStackInvalidConfigError("Invalid clouds.yaml.") from exc

    if not clouds:
        raise OpenStackInvalidConfigError("No clouds defined in clouds.yaml.")


def _write_openstack_config_to_disk(cloud_config: dict) -> None:
    """Write the cloud configuration to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to write to disk.
    """
    CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLOUDS_YAML_PATH.write_text(encoding="utf-8", data=yaml.dump(cloud_config))


def initialize_openstack(cloud_config: dict) -> None:
    """Initialize Openstack integration.

    Validates config and writes it to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    _validate_openstack_cloud_config(cloud_config)
    _write_openstack_config_to_disk(cloud_config)


class CharmConfig(BaseModel):
    """General charm configuration.

    Some charm configurations are grouped into other configuration models.

    Attributes:
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        token: GitHub personal access token for GitHub API.
        reconcile_interval: Time between each reconciliation of runners.
        denylist: List of IPv4 to block the runners from accessing.
        dockerhub_mirror: Private docker registry as dockerhub mirror for the runners to use.
        openstack_clouds_yaml: The openstack clouds.yaml configuration.
    """

    path: GithubPath
    token: str
    reconcile_interval: int
    denylist: list[FirewallEntry]
    dockerhub_mirror: str | None
    openstack_clouds_yaml: dict | None

    @classmethod
    def _parse_denylist(cls, charm: CharmBase) -> list[str]:
        denylist_str = charm.config.get("denylist", "")

        entry_list = [entry.strip() for entry in denylist_str.split(",")]
        denylist = [FirewallEntry.decode(entry) for entry in entry_list if entry]
        return denylist

    @classmethod
    def _parse_dockerhub_mirror(cls, charm: CharmBase) -> str | None:
        """Parse and validate dockerhub mirror URL.

        args:
            charm: The charm instance.

        Returns:
            The URL of dockerhub mirror.
        """
        dockerhub_mirror = charm.config.get("dockerhub-mirror") or None

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
        path_str = charm.config.get("path", "")
        if not path_str:
            raise CharmConfigInvalidError("Missing path configuration")
        runner_group = charm.config.get("group", "default")
        path = parse_github_path(path_str, runner_group)

        token = charm.config.get("token")
        if not token:
            raise CharmConfigInvalidError("Missing token configuration")

        try:
            reconcile_interval = int(charm.config["reconcile-interval"])
        except ValueError as err:
            raise CharmConfigInvalidError("The reconcile-interval config must be int") from err

        denylist = cls._parse_denylist(charm)
        dockerhub_mirror = cls._parse_dockerhub_mirror(charm)

        openstack_clouds_yaml_str = charm.config.get(OPENSTACK_CLOUDS_YAML_CONFIG_NAME)
        if openstack_clouds_yaml_str:
            try:
                openstack_clouds_yaml = yaml.safe_load(openstack_clouds_yaml_str)
            except yaml.YAMLError as exc:
                logger.error("Invalid openstack-clouds-yaml config: %s.", exc)
                raise CharmConfigInvalidError(
                    "Invalid openstack-clouds-yaml config. Invalid yaml."
                ) from exc
            if (config_type := type(openstack_clouds_yaml)) is not dict:
                raise CharmConfigInvalidError(
                    f"Invalid openstack config format, expected dict, got {config_type}"
                )
            try:
                initialize_openstack(openstack_clouds_yaml)
            except OpenStackInvalidConfigError as exc:
                logger.error("Invalid openstack config, %s.", exc)
                raise CharmConfigInvalidError(
                    "Invalid openstack config. Not able to initialize openstack integration."
                ) from exc
        else:
            openstack_clouds_yaml = None

        return cls(
            path=path,
            token=token,
            reconcile_interval=reconcile_interval,
            denylist=denylist,
            dockerhub_mirror=dockerhub_mirror,
            openstack_clouds_yaml=openstack_clouds_yaml,
        )

    @root_validator
    @classmethod
    def check_fields(cls, values: dict) -> dict:
        """Validate the general charm configuration.

        Args:
            values: Values in the pydantic model.

        Returns:
            Modified values in the pydantic model.
        """
        reconcile_interval = cast(int, values.get("reconcile_interval"))

        # The EventTimer class sets a timeout of `reconcile_interval` - 1.
        # Therefore the `reconcile_interval` must be at least 2.
        if reconcile_interval < 2:
            logger.exception("The virtual-machines configuration must be int")
            raise ValueError(
                "The reconcile_interval configuration needs to be greater or equal to 2"
            )

        return values


class RunnerCharmConfig(BaseModel):
    """Runner configurations for the charm.

    Attributes:
        virtual_machines: Number of virtual machine-based runner to spawn.
        virtual_machine_resources: Hardware resource used by one virtual machine for a runner.
        runner_storage: Storage to be used as disk for the runner.
    """

    virtual_machines: int
    virtual_machine_resources: VirtualMachineResources
    runner_storage: RunnerStorage

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "RunnerCharmConfig":
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
            virtual_machines = int(charm.config["virtual-machines"])
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
        """Validate the runner configuration.

        Args:
            values: Values in the pydantic model.

        Returns:
            Modified values in the pydantic model.
        """
        virtual_machines = cast(int, values.get("virtual_machines"))
        resources = cast(VirtualMachineResources, values.get("virtual_machine_resources"))

        if virtual_machines < 0:
            raise ValueError(
                "The virtual-machines configuration needs to be greater or equal to 0"
            )

        if resources.cpu < 1:
            raise ValueError("The vm-cpu configuration needs to be greater than 0")
        if not _valid_storage_size_str(resources.memory):
            raise ValueError(
                "Invalid format for vm-memory configuration, must be int with unit (e.g. MiB, GiB)"
            )
        if not _valid_storage_size_str(resources.disk):
            raise ValueError(
                "Invalid format for vm-disk configuration, must be int with unit (e.g., MiB, GiB)"
            )

        return values


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
        """Validate the proxy configuration.

        Args:
            values: Values in the pydantic model.

        Returns:
            Modified values in the pydantic model.
        """
        if values.get("use_aproxy") and not (values.get("http") or values.get("https")):
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


def _get_supported_arch() -> Arch:
    """Get current machine architecture.

    Raises:
        UnsupportedArchitectureError: if the current architecture is unsupported.

    Returns:
        Arch: Current machine architecture.
    """
    arch = platform.machine()
    match arch:
        case arch if arch in ARCHITECTURES_ARM64:
            return Arch.ARM64
        case arch if arch in ARCHITECTURES_X86:
            return Arch.X64
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
class CharmState:
    """The charm state.

    Attributes:
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        charm_config: Configuration of the juju charm.
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Proxy-related configuration.
        ssh_debug_connections: SSH debug connections configuration information.
    """

    arch: Arch
    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    charm_config: CharmConfig
    runner_config: RunnerCharmConfig
    ssh_debug_connections: list[SSHDebugConnection]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "CharmState":
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
        except (ValidationError, ValueError) as exc:
            logger.error("Invalid proxy config: %s", exc)
            raise CharmConfigInvalidError(f"Invalid proxy configuration: {str(exc)}") from exc

        try:
            charm_config = CharmConfig.from_charm(charm)
        except (ValidationError, ValueError) as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc

        try:
            runner_config = RunnerCharmConfig.from_charm(charm)
        except (ValidationError, ValueError) as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc

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
            ssh_debug_connections = SSHDebugConnection.from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid SSH debug info: %s.", exc)
            raise CharmConfigInvalidError("Invalid SSH Debug info") from exc

        state = cls(
            arch=arch,
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            charm_config=charm_config,
            runner_config=runner_config,
            ssh_debug_connections=ssh_debug_connections,
        )

        state_dict = dataclasses.asdict(state)
        # Convert pydantic object to python object serializable by json module.
        state_dict["proxy_config"] = json.loads(state_dict["proxy_config"].json())
        state_dict["charm_config"] = json.loads(state_dict["charm_config"].json())
        state_dict["runner_config"] = json.loads(state_dict["runner_config"].json())
        state_dict["ssh_debug_connections"] = [
            debug_info.json() for debug_info in state_dict["ssh_debug_connections"]
        ]
        json_data = json.dumps(state_dict, ensure_ascii=False)
        CHARM_STATE_PATH.write_text(json_data, encoding="utf-8")

        return state
