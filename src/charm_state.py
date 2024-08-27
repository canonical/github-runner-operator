# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

# TODO: 2024-06-26 The charm contains a lot of states and configuration. The upcoming refactor will
# split each/related class to a file.
# pylint: disable=too-many-lines

"""State of the Charm."""

import dataclasses
import json
import logging
import platform
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, NamedTuple, Optional, cast
from urllib.parse import urlsplit

import yaml
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops import CharmBase
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    MongoDsn,
    ValidationError,
    field_validator,
)
from pydantic_core import Url

import openstack_cloud
from errors import MissingMongoDBError, OpenStackInvalidConfigError
from firewall import FirewallEntry
from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64"}

CHARM_STATE_PATH = Path("charm_state.json")

BASE_IMAGE_CONFIG_NAME = "base-image"
DENYLIST_CONFIG_NAME = "denylist"
DOCKERHUB_MIRROR_CONFIG_NAME = "dockerhub-mirror"
GROUP_CONFIG_NAME = "group"
LABELS_CONFIG_NAME = "labels"
OPENSTACK_CLOUDS_YAML_CONFIG_NAME = "openstack-clouds-yaml"
OPENSTACK_NETWORK_CONFIG_NAME = "openstack-network"
OPENSTACK_FLAVOR_CONFIG_NAME = "openstack-flavor"
PATH_CONFIG_NAME = "path"
RECONCILE_INTERVAL_CONFIG_NAME = "reconcile-interval"
# bandit thinks this is a hardcoded password
REPO_POLICY_COMPLIANCE_TOKEN_CONFIG_NAME = "repo-policy-compliance-token"  # nosec
REPO_POLICY_COMPLIANCE_URL_CONFIG_NAME = "repo-policy-compliance-url"
RUNNER_STORAGE_CONFIG_NAME = "runner-storage"
SENSITIVE_PLACEHOLDER = "*****"
TEST_MODE_CONFIG_NAME = "test-mode"
# bandit thinks this is a hardcoded password.
TOKEN_CONFIG_NAME = "token"  # nosec
USE_APROXY_CONFIG_NAME = "experimental-use-aproxy"
VIRTUAL_MACHINES_CONFIG_NAME = "virtual-machines"
VM_CPU_CONFIG_NAME = "vm-cpu"
VM_MEMORY_CONFIG_NAME = "vm-memory"
VM_DISK_CONFIG_NAME = "vm-disk"

# Integration names
COS_AGENT_INTEGRATION_NAME = "cos-agent"
DEBUG_SSH_INTEGRATION_NAME = "debug-ssh"
IMAGE_INTEGRATION_NAME = "image"
MONGO_DB_INTEGRATION_NAME = "mongodb"

StorageSize = str
"""Representation of storage size with KiB, MiB, GiB, TiB, PiB, EiB as unit."""


def validate_https(url: AnyHttpUrl) -> AnyHttpUrl:
    if url.scheme == "https":
        return url

    raise ValueError("URL: %s is not a valid https url!", url)


AnyHttpsUrl = Annotated[AnyHttpUrl, AfterValidator(validate_https)]


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

    Raises:
        CharmConfigInvalidError: if an invalid path string was given.

    Returns:
        GithubPath object representing the GitHub repository, or the GitHub
        organization with runner group information.
    """
    if "/" in path_str:
        paths = tuple(segment for segment in path_str.split("/") if segment)
        if len(paths) != 2:
            raise CharmConfigInvalidError(f"Invalid path configuration {path_str}")
        owner, repo = paths
        return GithubRepo(owner=owner, repo=repo)
    return GithubOrg(org=path_str, group=runner_group)


@dataclasses.dataclass
class GithubConfig:
    """Charm configuration related to GitHub.

    Attributes:
        token: The Github API access token (PAT).
        path: The Github org/repo path.
    """

    token: str
    path: GithubPath

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "GithubConfig":
        """Get github related charm configuration values from charm.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: If an invalid configuration value was set.

        Returns:
            The parsed GitHub configuration values.
        """
        runner_group = cast(str, charm.config.get(GROUP_CONFIG_NAME, "default"))

        path_str = cast(str, charm.config.get(PATH_CONFIG_NAME, ""))
        if not path_str:
            raise CharmConfigInvalidError(f"Missing {PATH_CONFIG_NAME} configuration")
        path = parse_github_path(cast(str, path_str), cast(str, runner_group))

        token = cast(str, charm.config.get(TOKEN_CONFIG_NAME))
        if not token:
            raise CharmConfigInvalidError(f"Missing {TOKEN_CONFIG_NAME} configuration")

        return cls(token=cast(str, token), path=path)


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
    """Supported system architectures.

    Attributes:
        ARM64: Represents an ARM64 system architecture.
        X64: Represents an X64/AMD64 system architecture.
    """

    ARM64 = "arm64"
    X64 = "x64"


class RunnerStorage(str, Enum):
    """Supported storage as runner disk.

    Attributes:
        JUJU_STORAGE: Represents runner storage from Juju storage.
        MEMORY: Represents tempfs storage (ramdisk).
    """

    JUJU_STORAGE = "juju-storage"
    MEMORY = "memory"


class InstanceType(str, Enum):
    """Type of instance for runner.

    Attributes:
        LOCAL_LXD: LXD instance on the local juju machine.
        OPENSTACK: OpenStack instance on a cloud.
    """

    LOCAL_LXD = "local_lxd"
    OPENSTACK = "openstack"


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


WORD_ONLY_REGEX = re.compile("^[\\w\\-]+$")


def _parse_labels(labels: str) -> tuple[str, ...]:
    """Return valid labels.

    Args:
        labels: Comma separated labels string.

    Raises:
        ValueError: if any invalid label was found.

    Returns:
        Labels consisting of alphanumeric and underscore only.
    """
    invalid_labels = []
    valid_labels = []
    for label in labels.split(","):
        stripped_label = label.strip()
        if not stripped_label:
            continue
        if not WORD_ONLY_REGEX.match(stripped_label):
            invalid_labels.append(stripped_label)
        else:
            valid_labels.append(stripped_label)

    if invalid_labels:
        raise ValueError(f"Invalid labels {','.join(invalid_labels)} found.")

    return tuple(valid_labels)


class RepoPolicyComplianceConfig(BaseModel):
    """Configuration for the repo policy compliance service.

    Attributes:
        token: Token for the repo policy compliance service.
        url: URL of the repo policy compliance service.
    """

    token: str
    url: AnyHttpUrl

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "RepoPolicyComplianceConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: If an invalid configuration was set.

        Returns:
            Current repo-policy-compliance config.
        """
        token = charm.config.get(REPO_POLICY_COMPLIANCE_TOKEN_CONFIG_NAME)
        if not token:
            raise CharmConfigInvalidError(
                f"Missing {REPO_POLICY_COMPLIANCE_TOKEN_CONFIG_NAME} configuration"
            )
        url = charm.config.get(REPO_POLICY_COMPLIANCE_URL_CONFIG_NAME)
        if not url:
            raise CharmConfigInvalidError(
                f"Missing {REPO_POLICY_COMPLIANCE_URL_CONFIG_NAME} configuration"
            )

        # pydantic allows string to be passed as AnyHttpUrl, mypy complains about it
        return cls(url=url, token=token)  # type: ignore


class CharmConfig(BaseModel):
    """General charm configuration.

    Some charm configurations are grouped into other configuration models.

    Attributes:
        denylist: List of IPv4 to block the runners from accessing.
        dockerhub_mirror: Private docker registry as dockerhub mirror for the runners to use.
        labels: Additional runner labels to append to default (i.e. os, flavor, architecture).
        openstack_clouds_yaml: The openstack clouds.yaml configuration.
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        reconcile_interval: Time between each reconciliation of runners in minutes.
        repo_policy_compliance: Configuration for the repo policy compliance service.
        token: GitHub personal access token for GitHub API.
    """

    denylist: list[FirewallEntry]
    dockerhub_mirror: AnyHttpsUrl | None = None
    labels: tuple[str, ...]
    openstack_clouds_yaml: dict[str, dict] | None = None
    path: GithubPath
    reconcile_interval: int
    repo_policy_compliance: RepoPolicyComplianceConfig | None = None
    token: str

    @classmethod
    def _parse_denylist(cls, charm: CharmBase) -> list[FirewallEntry]:
        """Read charm denylist configuration and parse it into firewall deny entries.

        Args:
            charm: The charm instance.

        Returns:
            The firewall deny entries.
        """
        denylist_str = cast(str, charm.config.get(DENYLIST_CONFIG_NAME, ""))

        entry_list = [entry.strip() for entry in denylist_str.split(",")]
        denylist = [FirewallEntry.decode(entry) for entry in entry_list if entry]
        return denylist

    # *** docker hub mirror url changed from a string to an https url ***
    @classmethod
    def _parse_dockerhub_mirror(cls, charm: CharmBase) -> str | None:
        """Parse and validate dockerhub mirror URL.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: if insecure scheme is passed for dockerhub mirror.

        Returns:
            The URL of dockerhub mirror.
        """
        dockerhub_mirror: str | None = (
            cast(str, charm.config.get(DOCKERHUB_MIRROR_CONFIG_NAME)) or None
        )

        if not dockerhub_mirror:
            return None

        dockerhub_mirror = cast(str, dockerhub_mirror)
        dockerhub_mirror_url = urlsplit(dockerhub_mirror)
        if dockerhub_mirror_url.scheme != "https":
            raise CharmConfigInvalidError(
                (
                    f"Only secured registry supported for {DOCKERHUB_MIRROR_CONFIG_NAME} "
                    "configuration, the scheme should be https"
                )
            )

        return dockerhub_mirror

    @classmethod
    def _parse_openstack_clouds_config(cls, charm: CharmBase) -> dict | None:
        """Parse and validate openstack clouds yaml config value.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: if an invalid Openstack config value was set.

        Returns:
            The openstack clouds yaml.
        """
        openstack_clouds_yaml_str: str | None = cast(
            str, charm.config.get(OPENSTACK_CLOUDS_YAML_CONFIG_NAME)
        )
        if not openstack_clouds_yaml_str:
            return None

        try:
            openstack_clouds_yaml = yaml.safe_load(cast(str, openstack_clouds_yaml_str))
        except yaml.YAMLError as exc:
            logger.error(f"Invalid {OPENSTACK_CLOUDS_YAML_CONFIG_NAME} config: %s.", exc)
            raise CharmConfigInvalidError(
                f"Invalid {OPENSTACK_CLOUDS_YAML_CONFIG_NAME} config. Invalid yaml."
            ) from exc
        if (config_type := type(openstack_clouds_yaml)) is not dict:
            raise CharmConfigInvalidError(
                f"Invalid openstack config format, expected dict, got {config_type}"
            )
        try:
            openstack_cloud.initialize(openstack_clouds_yaml)
        except OpenStackInvalidConfigError as exc:
            logger.error("Invalid openstack config, %s.", exc)
            raise CharmConfigInvalidError(
                "Invalid openstack config. Not able to initialize openstack integration."
            ) from exc

        return cast(dict, openstack_clouds_yaml)

    @field_validator("reconcile_interval")
    @classmethod
    def check_reconcile_interval(cls, reconcile_interval: int) -> int:
        """Validate the general charm configuration.

        Args:
            reconcile_interval: The value of reconcile_interval passed to class instantiation.

        Raises:
            ValueError: if an invalid reconcile_interval value of less than 2 has been passed.

        Returns:
            The validated reconcile_interval value.
        """
        # The EventTimer class sets a timeout of `reconcile_interval` - 1.
        # Therefore the `reconcile_interval` must be at least 2.
        if reconcile_interval < 2:
            logger.error(
                "The %s configuration must be greater than 1", RECONCILE_INTERVAL_CONFIG_NAME
            )
            raise ValueError(
                f"The {RECONCILE_INTERVAL_CONFIG_NAME} configuration needs to be greater or equal"
                " to 2"
            )

        return reconcile_interval

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "CharmConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: If any invalid configuration has been set on the charm.

        Returns:
            Current config of the charm.
        """
        try:
            github_config = GithubConfig.from_charm(charm)
        except CharmConfigInvalidError as exc:
            raise CharmConfigInvalidError(f"Invalid Github config, {str(exc)}") from exc

        try:
            reconcile_interval = int(charm.config[RECONCILE_INTERVAL_CONFIG_NAME])
        except ValueError as err:
            raise CharmConfigInvalidError(
                f"The {RECONCILE_INTERVAL_CONFIG_NAME} config must be int"
            ) from err

        denylist = cls._parse_denylist(charm)
        dockerhub_mirror = cast(str, charm.config.get(DOCKERHUB_MIRROR_CONFIG_NAME, "")) or None
        openstack_clouds_yaml = cls._parse_openstack_clouds_config(charm)

        try:
            labels = _parse_labels(cast(str, charm.config.get(LABELS_CONFIG_NAME, "")))
        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid {LABELS_CONFIG_NAME} config: {exc}") from exc

        repo_policy_compliance = None
        if charm.config.get(REPO_POLICY_COMPLIANCE_TOKEN_CONFIG_NAME) or charm.config.get(
            REPO_POLICY_COMPLIANCE_URL_CONFIG_NAME
        ):
            if not openstack_clouds_yaml:
                raise CharmConfigInvalidError(
                    "Cannot use repo-policy-compliance config without using OpenStack."
                )
            repo_policy_compliance = RepoPolicyComplianceConfig.from_charm(charm)

        # pydantic allows to pass str as AnyHttpUrl, mypy complains about it
        return cls(
            denylist=denylist,
            dockerhub_mirror=dockerhub_mirror,  # type: ignore
            labels=labels,
            openstack_clouds_yaml=openstack_clouds_yaml,
            path=github_config.path,
            reconcile_interval=reconcile_interval,
            repo_policy_compliance=repo_policy_compliance,
            token=github_config.token,
        )


LTS_IMAGE_VERSION_TAG_MAP = {"22.04": "jammy", "24.04": "noble"}


class BaseImage(str, Enum):
    """The ubuntu OS base image to build and deploy runners on.

    Attributes:
        JAMMY: The jammy ubuntu LTS image.
        NOBLE: The noble ubuntu LTS image.
    """

    JAMMY = "jammy"
    NOBLE = "noble"

    def __str__(self) -> str:
        """Interpolate to string value.

        Returns:
            The enum string value.
        """
        return self.value

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "BaseImage":
        """Retrieve the base image tag from charm.

        Args:
            charm: The charm instance.

        Returns:
            The base image configuration of the charm.
        """
        image_name = cast(str, charm.config.get(BASE_IMAGE_CONFIG_NAME, "jammy")).lower().strip()
        if image_name in LTS_IMAGE_VERSION_TAG_MAP:
            return cls(LTS_IMAGE_VERSION_TAG_MAP[image_name])
        return cls(image_name)


class OpenstackImage(BaseModel):
    """OpenstackImage from image builder relation data.

    Attributes:
        id: The OpenStack image ID.
        tags: Image tags, e.g. jammy
    """

    id: str | None = None
    tags: list[str] | None = None

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "OpenstackImage | None":
        """Initialize the OpenstackImage info from relation data.

        None represents relation not established.
        None values for id/tags represent image not yet ready but the relation exists.

        Args:
            charm: The charm instance.

        Returns:
            OpenstackImage metadata from charm relation data.
        """
        relations = charm.model.relations[IMAGE_INTEGRATION_NAME]
        if not relations or not (relation := relations[0]).units:
            return None
        for unit in relation.units:
            relation_data = relation.data[unit]
            if not relation_data:
                continue
            return OpenstackImage(
                id=relation_data.get("id", None),
                tags=[tag.strip() for tag in relation_data.get("tags", "").split(",") if tag],
            )
        return OpenstackImage(id=None, tags=None)


class OpenstackRunnerConfig(BaseModel):
    """Runner configuration for OpenStack Instances.

    Attributes:
        virtual_machines: Number of virtual machine-based runner to spawn.
        openstack_flavor: flavor on openstack to use for virtual machines.
        openstack_network: Network on openstack to use for virtual machines.
        openstack_image: Openstack image to use for virtual machines.
    """

    virtual_machines: int
    openstack_flavor: str
    openstack_network: str
    openstack_image: OpenstackImage | None = None

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "OpenstackRunnerConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: Error with charm configuration virtual-machines not of int
                type.

        Returns:
            Openstack runner config of the charm.
        """
        try:
            virtual_machines = int(charm.config["virtual-machines"])
        except ValueError as err:
            raise CharmConfigInvalidError(
                "The virtual-machines configuration must be int"
            ) from err

        openstack_flavor = charm.config[OPENSTACK_FLAVOR_CONFIG_NAME]
        openstack_network = charm.config[OPENSTACK_NETWORK_CONFIG_NAME]
        openstack_image = OpenstackImage.from_charm(charm)

        return cls(
            virtual_machines=virtual_machines,
            openstack_flavor=cast(str, openstack_flavor),
            openstack_network=cast(str, openstack_network),
            openstack_image=openstack_image,
        )


class LocalLxdRunnerConfig(BaseModel):
    """Runner configurations for local LXD instances.

    Attributes:
        base_image: The ubuntu base image to run the runner virtual machines on.
        virtual_machines: Number of virtual machine-based runner to spawn.
        virtual_machine_resources: Hardware resource used by one virtual machine for a runner.
        runner_storage: Storage to be used as disk for the runner.
    """

    base_image: BaseImage
    virtual_machines: int
    virtual_machine_resources: VirtualMachineResources
    runner_storage: RunnerStorage

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "LocalLxdRunnerConfig":
        """Initialize the config from charm.

        Args:
            charm: The charm instance.

        Raises:
            CharmConfigInvalidError: if an invalid runner charm config has been set on the charm.

        Returns:
            Local LXD runner config of the charm.
        """
        try:
            base_image = BaseImage.from_charm(charm)
        except ValueError as err:
            raise CharmConfigInvalidError("Invalid base image") from err

        try:
            runner_storage = RunnerStorage(charm.config[RUNNER_STORAGE_CONFIG_NAME])
        except ValueError as err:
            raise CharmConfigInvalidError(
                f"Invalid {RUNNER_STORAGE_CONFIG_NAME} configuration"
            ) from err
        except CharmConfigInvalidError as exc:
            raise CharmConfigInvalidError(f"Invalid runner storage config, {str(exc)}") from exc

        try:
            virtual_machines = int(charm.config[VIRTUAL_MACHINES_CONFIG_NAME])
        except ValueError as err:
            raise CharmConfigInvalidError(
                f"The {VIRTUAL_MACHINES_CONFIG_NAME} configuration must be int"
            ) from err

        try:
            cpu = int(charm.config[VM_CPU_CONFIG_NAME])
        except ValueError as err:
            raise CharmConfigInvalidError(f"Invalid {VM_CPU_CONFIG_NAME} configuration") from err

        virtual_machine_resources = VirtualMachineResources(
            cpu,
            cast(str, charm.config[VM_MEMORY_CONFIG_NAME]),
            cast(str, charm.config[VM_DISK_CONFIG_NAME]),
        )

        return cls(
            base_image=base_image,
            virtual_machines=virtual_machines,
            virtual_machine_resources=virtual_machine_resources,
            runner_storage=runner_storage,
        )

    @field_validator("virtual_machines")
    @classmethod
    def check_virtual_machines(cls, virtual_machines: int) -> int:
        """Validate the virtual machines configuration value.

        Args:
            virtual_machines: The virtual machines value to validate.

        Raises:
            ValueError: if a negative integer was passed.

        Returns:
            Validated virtual_machines value.
        """
        if virtual_machines < 0:
            raise ValueError(
                f"The {VIRTUAL_MACHINES_CONFIG_NAME} configuration needs to be greater or equal "
                "to 0"
            )

        return virtual_machines

    @field_validator("virtual_machine_resources")
    @classmethod
    def check_virtual_machine_resources(
        cls, vm_resources: VirtualMachineResources
    ) -> VirtualMachineResources:
        """Validate the virtual_machine_resources field values.

        Args:
            vm_resources: the virtual_machine_resources value to validate.

        Raises:
            ValueError: if an invalid number of cpu was given or invalid memory/disk size was
                given.

        Returns:
            The validated virtual_machine_resources value.
        """
        if vm_resources.cpu < 1:
            raise ValueError(f"The {VM_CPU_CONFIG_NAME} configuration needs to be greater than 0")
        if not _valid_storage_size_str(vm_resources.memory):
            raise ValueError(
                f"Invalid format for {VM_MEMORY_CONFIG_NAME} configuration, must be int with unit "
                "(e.g. MiB, GiB)"
            )
        if not _valid_storage_size_str(vm_resources.disk):
            raise ValueError(
                f"Invalid format for {VM_DISK_CONFIG_NAME} configuration, must be int with unit "
                "(e.g., MiB, GiB)"
            )

        return vm_resources


RunnerConfig = OpenstackRunnerConfig | LocalLxdRunnerConfig


class ProxyConfig(BaseModel):
    """Proxy configuration.

    Attributes:
        aproxy_address: The address of aproxy snap instance if use_aproxy is enabled.
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
        use_aproxy: Whether aproxy should be used for the runners.
    """

    http: Optional[AnyHttpUrl] = None
    https: Optional[AnyHttpUrl] = None
    no_proxy: Optional[str] = None
    use_aproxy: bool = False

    @property
    def aproxy_address(self) -> Optional[str]:
        """Return the aproxy address."""
        if self.use_aproxy:
            proxy_address = self.http or self.https
            # assert is only used to make mypy happy
            assert (
                proxy_address is not None and proxy_address.host is not None
            )  # nosec for [B101:assert_used]
            aproxy_address = proxy_address.host
        else:
            aproxy_address = None
        return aproxy_address

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @field_validator("use_aproxy")
    @classmethod
    def check_use_aproxy(cls, use_aproxy: bool, values: dict) -> bool:
        """Validate the proxy configuration.

        Args:
            use_aproxy: Value of use_aproxy variable.
            values: Values in the pydantic model.

        Raises:
            ValueError: if use_aproxy was set but no http/https was passed.

        Returns:
            Validated use_aproxy value.
        """
        try:
            if use_aproxy and not (values.data.get("http") or values.data.get("https")):
                raise ValueError("aproxy requires http or https to be set")
        except (
            AttributeError
        ) as e:  # needed because when http or https are not passed, it raises an AttributeError
            raise ValueError("aproxy requires http or https to be set")

        return use_aproxy

    def __bool__(self) -> bool:
        """Return whether the proxy config is set.

        Returns:
            Whether the proxy config is set.
        """
        return bool(self.http or self.https)

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "ProxyConfig":
        """Initialize the proxy config from charm.

        Args:
            charm: The charm instance.

        Returns:
            Current proxy config of the charm.
        """
        use_aproxy = bool(charm.config.get(USE_APROXY_CONFIG_NAME))
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

    # TODO[pydantic]: The following keys were removed: `allow_mutation`.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    model_config = ConfigDict(allow_mutation=False)


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

        Returns:
            List of connection information for ssh debug access.
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
                # pydantic allows string to be passed as IPvAnyAddress and as int,
                # mypy complains about it
                SSHDebugConnection(
                    host=host,  # type: ignore
                    port=port,  # type: ignore
                    rsa_fingerprint=rsa_fingerprint,
                    ed25519_fingerprint=ed25519_fingerprint,
                )
            )
        return ssh_debug_connections


class ReactiveConfig(BaseModel):
    """Represents the configuration for reactive scheduling.

    Attributes:
        mq_uri: The URI of the MQ to use to spawn runners reactively.
    """

    mq_uri: MongoDsn

    @classmethod
    def from_database(cls, database: DatabaseRequires) -> "ReactiveConfig | None":
        """Initialize the ReactiveConfig from charm config and integration data.

        Args:
            database: The database to fetch integration data from.

        Returns:
            The connection information for the reactive MQ or None if not available.

        Raises:
            MissingMongoDBError: If the information on howto access MongoDB
                is missing in the integration data.
        """
        integration_existing = bool(database.relations)

        if not integration_existing:
            return None

        uri_field = "uris"  # the field is called uris though it's a single uri
        relation_data = list(database.fetch_relation_data(fields=[uri_field]).values())

        # There can be only one database integrated at a time
        # with the same interface name. See: metadata.yaml
        data = relation_data[0]

        if uri_field in data:
            return ReactiveConfig(mq_uri=data[uri_field])

        raise MissingMongoDBError(
            f"Missing {uri_field} for {MONGO_DB_INTEGRATION_NAME} integration"
        )


class ImmutableConfigChangedError(Exception):
    """Represents an error when changing immutable charm state."""

    def __init__(self, msg: str):
        """Initialize a new instance of the ImmutableConfigChangedError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


# Charm State is a list of all the configurations and states of the charm and
# has therefore a lot of attributes.
@dataclasses.dataclass(frozen=True)
class CharmState:  # pylint: disable=too-many-instance-attributes
    """The charm state.

    Attributes:
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        charm_config: Configuration of the juju charm.
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Proxy-related configuration.
        instance_type: The type of instances, e.g., local lxd, openstack.
        reactive_config: The charm configuration related to reactive spawning mode.
        runner_config: The charm configuration related to runner VM configuration.
        ssh_debug_connections: SSH debug connections configuration information.
    """

    arch: Arch
    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    instance_type: InstanceType
    charm_config: CharmConfig
    runner_config: RunnerConfig
    reactive_config: ReactiveConfig | None
    ssh_debug_connections: list[SSHDebugConnection]

    @classmethod
    def _store_state(cls, state: "CharmState") -> None:
        """Store the state of the charm to disk.

        Args:
            state: The state of the charm.
        """
        state_dict = dataclasses.asdict(state)
        # Convert pydantic object to python object serializable by json module.
        state_dict["proxy_config"] = json.loads(state_dict["proxy_config"].json())
        state_dict["charm_config"] = json.loads(state_dict["charm_config"].json())
        if state.reactive_config:
            state_dict["reactive_config"] = json.loads(state_dict["reactive_config"].json())
        state_dict["runner_config"] = json.loads(state_dict["runner_config"].json())
        state_dict["ssh_debug_connections"] = [
            debug_info.json() for debug_info in state_dict["ssh_debug_connections"]
        ]
        json_data = json.dumps(state_dict, ensure_ascii=False)
        CHARM_STATE_PATH.write_text(json_data, encoding="utf-8")

    @classmethod
    def _check_immutable_config_change(
        cls, runner_storage: RunnerStorage, base_image: BaseImage
    ) -> None:
        """Ensure immutable config has not changed.

        Args:
            runner_storage: The current runner_storage configuration.
            base_image: The current base_image configuration.

        Raises:
            ImmutableConfigChangedError: If an immutable configuration has changed.
        """
        if not CHARM_STATE_PATH.exists():
            return

        json_data = CHARM_STATE_PATH.read_text(encoding="utf-8")
        prev_state = json.loads(json_data)

        cls._log_prev_state(prev_state)

        try:
            if prev_state["runner_config"]["runner_storage"] != runner_storage:
                logger.error(
                    "Storage option changed from %s to %s, blocking the charm",
                    prev_state["runner_config"]["runner_storage"],
                    runner_storage,
                )
                raise ImmutableConfigChangedError(
                    msg=(
                        "runner-storage config cannot be changed after deployment, "
                        "redeploy if needed"
                    )
                )
        except KeyError as exc:
            logger.info("Key %s not found, this will be updated to current config.", exc.args[0])

        try:
            if prev_state["runner_config"]["base_image"] != base_image.value:
                logger.error(
                    "Base image option changed from %s to %s, blocking the charm",
                    prev_state["runner_config"]["base_image"],
                    runner_storage,
                )
                raise ImmutableConfigChangedError(
                    msg="base-image config cannot be changed after deployment, redeploy if needed"
                )
        except KeyError as exc:
            logger.info("Key %s not found, this will be updated to current config.", exc.args[0])

    @classmethod
    def _log_prev_state(cls, prev_state_dict: dict) -> None:
        """Log the previous state of the charm.

        Replace sensitive information before logging.

        Args:
            prev_state_dict: The previous state of the charm as a dict.
        """
        if logger.isEnabledFor(logging.DEBUG):
            prev_state_for_logging = prev_state_dict.copy()
            charm_config = prev_state_for_logging.get("charm_config")
            if charm_config and "token" in charm_config:
                charm_config = charm_config.copy()
                charm_config["token"] = SENSITIVE_PLACEHOLDER  # nosec
            prev_state_for_logging["charm_config"] = charm_config

            reactive_config = prev_state_for_logging.get("reactive_config")
            if reactive_config and "mq_uri" in reactive_config:
                reactive_config = reactive_config.copy()
                reactive_config["mq_uri"] = "*****"
            prev_state_for_logging["reactive_config"] = reactive_config

            logger.debug("Previous charm state: %s", prev_state_for_logging)

    # Ignore the flake8 function too complex (C901). The function does not have much logic, the
    # lint is likely triggered with the multiple try-excepts, which are needed.
    @classmethod
    def from_charm(  # noqa: C901
        cls, charm: CharmBase, database: DatabaseRequires
    ) -> "CharmState":
        """Initialize the state from charm.

        Args:
            charm: The charm instance.
            database: The database instance.

        Raises:
            CharmConfigInvalidError: If an invalid configuration was set.

        Returns:
            Current state of the charm.
        """
        try:
            proxy_config = ProxyConfig.from_charm(charm)
        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid proxy configuration: {str(exc)}") from exc

        try:
            charm_config = CharmConfig.from_charm(charm)
        except ValueError as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc

        try:
            runner_config: RunnerConfig
            if charm_config.openstack_clouds_yaml is not None:
                instance_type = InstanceType.OPENSTACK
                runner_config = OpenstackRunnerConfig.from_charm(charm)
            else:
                instance_type = InstanceType.LOCAL_LXD
                runner_config = LocalLxdRunnerConfig.from_charm(charm)
                cls._check_immutable_config_change(
                    runner_storage=runner_config.runner_storage,
                    base_image=runner_config.base_image,
                )
        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc
        except ImmutableConfigChangedError as exc:
            raise CharmConfigInvalidError(exc.msg) from exc

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

        reactive_config = ReactiveConfig.from_database(database)

        state = cls(
            arch=arch,
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            charm_config=charm_config,
            runner_config=runner_config,
            reactive_config=reactive_config,
            ssh_debug_connections=ssh_debug_connections,
            instance_type=instance_type,
        )

        cls._store_state(state)

        return state
