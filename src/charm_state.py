# Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import ipaddress
import json
import logging
import re
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

import yaml
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from github_runner_manager.configuration import ProxyConfig, SSHDebugConnection
from github_runner_manager.configuration.github import GitHubPath, parse_github_path
from ops import CharmBase
from pydantic import BaseModel, MongoDsn, ValidationError, create_model_from_typeddict, validator

from errors import MissingMongoDBError
from models import AnyHttpsUrl, FlavorLabel, OpenStackCloudsYAML
from utilities import get_env_var

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64"}

CHARM_STATE_PATH = Path("charm_state.json")

ALLOW_EXTERNAL_CONTRIBUTOR_CONFIG_NAME = "allow-external-contributor"
BASE_VIRTUAL_MACHINES_CONFIG_NAME = "base-virtual-machines"
DOCKERHUB_MIRROR_CONFIG_NAME = "dockerhub-mirror"
FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME = "flavor-label-combinations"
GROUP_CONFIG_NAME = "group"
LABELS_CONFIG_NAME = "labels"
MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME = "max-total-virtual-machines"
MANAGER_SSH_PROXY_COMMAND_CONFIG_NAME = "manager-ssh-proxy-command"
OPENSTACK_CLOUDS_YAML_CONFIG_NAME = "openstack-clouds-yaml"
OPENSTACK_NETWORK_CONFIG_NAME = "openstack-network"
OPENSTACK_FLAVOR_CONFIG_NAME = "openstack-flavor"
PATH_CONFIG_NAME = "path"
RECONCILE_INTERVAL_CONFIG_NAME = "reconcile-interval"
RUNNER_HTTP_PROXY_CONFIG_NAME = "runner-http-proxy"
SENSITIVE_PLACEHOLDER = "*****"
TEST_MODE_CONFIG_NAME = "test-mode"
# bandit thinks this is a hardcoded password.
TOKEN_CONFIG_NAME = "token"  # nosec
USE_APROXY_CONFIG_NAME = "experimental-use-aproxy"
APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME = "aproxy-exclude-addresses"
APROXY_REDIRECT_PORTS_CONFIG_NAME = "aproxy-redirect-ports"
USE_RUNNER_PROXY_FOR_TMATE_CONFIG_NAME = "use-runner-proxy-for-tmate"
VIRTUAL_MACHINES_CONFIG_NAME = "virtual-machines"
CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME = "pre-job-script"
RUNNER_MANAGER_LOG_LEVEL_CONFIG_NAME = "runner-manager-log-level"

# Integration names
COS_AGENT_INTEGRATION_NAME = "cos-agent"
DEBUG_SSH_INTEGRATION_NAME = "debug-ssh"
IMAGE_INTEGRATION_NAME = "image"
MONGO_DB_INTEGRATION_NAME = "mongodb"

LogLevel = Literal["CRITICAL", "FATAL", "ERROR", "WARNING", "INFO", "DEBUG"]


@dataclasses.dataclass
class GithubConfig:
    """Charm configuration related to GitHub.

    Attributes:
        token: The Github API access token (PAT).
        path: The Github org/repo path.
    """

    token: str
    path: GitHubPath

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "GithubConfig | None":
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
        token = cast(str, charm.config.get(TOKEN_CONFIG_NAME))

        if not path_str:
            raise CharmConfigInvalidError(f"Missing {PATH_CONFIG_NAME} configuration")

        try:
            path = parse_github_path(cast(str, path_str), cast(str, runner_group))
        except ValueError as e:
            raise CharmConfigInvalidError(str(e)) from e

        if not token:
            raise CharmConfigInvalidError(f"Missing {TOKEN_CONFIG_NAME} configuration")

        return cls(token=cast(str, token), path=path)


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


class CharmConfig(BaseModel):
    """General charm configuration.

    Some charm configurations are grouped into other configuration models.

    Attributes:
        allow_external_contributor: Whether to allow runs from forked repositories with from
            an external contributor with author association status less than COLLABORATOR. See \
            https://docs.github.com/en/graphql/reference/enums#commentauthorassociation.
        dockerhub_mirror: Private docker registry as dockerhub mirror for the runners to use.
        labels: Additional runner labels to append to default (i.e. os, flavor, architecture).
        openstack_clouds_yaml: The openstack clouds.yaml configuration.
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        reconcile_interval: Time between each reconciliation of runners in minutes.
        token: GitHub personal access token for GitHub API.
        manager_proxy_command: ProxyCommand for the SSH connection from the manager to the runner.
        use_aproxy: Whether to use aproxy in the runner.
        aproxy_exclude_addresses: a list of addresses to exclude from the aproxy proxy.
        aproxy_redirect_ports: a list of ports to redirect to the aproxy proxy.
        custom_pre_job_script: Custom pre-job script to run before the job.
        runner_manager_log_level: The log level of the runner manager application.
    """

    allow_external_contributor: bool
    dockerhub_mirror: AnyHttpsUrl | None
    labels: tuple[str, ...]
    openstack_clouds_yaml: OpenStackCloudsYAML
    path: GitHubPath | None
    reconcile_interval: int
    token: str | None
    manager_proxy_command: str | None
    use_aproxy: bool
    aproxy_exclude_addresses: list[str] = []
    aproxy_redirect_ports: list[str] = []
    custom_pre_job_script: str | None
    runner_manager_log_level: LogLevel

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
    def _parse_openstack_clouds_config(cls, charm: CharmBase) -> OpenStackCloudsYAML:
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
            raise CharmConfigInvalidError("No openstack_clouds_yaml")

        try:
            openstack_clouds_yaml: OpenStackCloudsYAML = yaml.safe_load(
                cast(str, openstack_clouds_yaml_str)
            )
            # use Pydantic to validate TypedDict.
            create_model_from_typeddict(OpenStackCloudsYAML)(**openstack_clouds_yaml)
        except (yaml.YAMLError, TypeError) as exc:
            logger.error(f"Invalid {OPENSTACK_CLOUDS_YAML_CONFIG_NAME} config: %s.", exc)
            raise CharmConfigInvalidError(
                f"Invalid {OPENSTACK_CLOUDS_YAML_CONFIG_NAME} config. Invalid yaml."
            ) from exc

        return openstack_clouds_yaml

    @validator("reconcile_interval")
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
        # The reconcile_interval should be at least 2.
        # Due to possible race condition with the message acknowledgement with job status checking
        # in reactive process.
        if reconcile_interval < 2:
            logger.error(
                "The %s configuration must be greater than or equal to 1",
                RECONCILE_INTERVAL_CONFIG_NAME,
            )
            raise ValueError(
                f"The {RECONCILE_INTERVAL_CONFIG_NAME} configuration needs to be greater or equal"
                " to 1"
            )

        return reconcile_interval

    @staticmethod
    def _parse_list(input_: str | list[str] | None) -> list[str]:
        """Split a comma-separated list of strings into a list of strings.

        Args:
            input_: The comma-separated list of strings.

        Returns:
            A list of strings.
        """
        if input_ is None:
            return []
        if isinstance(input_, str):
            input_ = input_.split(",")
        return [i.strip() for i in input_ if i.strip()]

    @validator("aproxy_exclude_addresses", pre=True)
    @classmethod
    def check_aproxy_exclude_addresses(
        cls, aproxy_exclude_addresses: list[str] | str | None
    ) -> list[str]:
        """Parse and validate aproxy_exclude_addresses config value.

        Args:
            aproxy_exclude_addresses: The aproxy_exclude_addresses configuration input.

        Raises:
            CharmConfigInvalidError: invalid aproxy_exclude_addresses configuration input.

        Returns:
            Parsed aproxy_exclude_addresses configuration input.
        """
        aproxy_exclude_addresses = cls._parse_list(aproxy_exclude_addresses)
        result = []
        for address_range in aproxy_exclude_addresses:
            if not address_range:
                continue
            if "-" in address_range:
                start, _, end = address_range.partition("-")
                if not start:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME} config, "
                        f"in {repr(address_range)}, missing start in range"
                    )
                if not end:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME} config, "
                        f"in {repr(address_range)}, missing end in range"
                    )
                try:
                    ipaddress.ip_address(start)
                    ipaddress.ip_address(end)
                except ValueError as exc:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME} config, "
                        f"in {repr(address_range)}, not an IP address"
                    ) from exc
            else:
                try:
                    ipaddress.ip_network(address_range, strict=False)
                except ValueError as exc:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME} config"
                        f"in {repr(address_range)}, not an IP address"
                    ) from exc
            result.append(address_range)
        return result

    @validator("aproxy_redirect_ports", pre=True)
    @classmethod
    def check_aproxy_redirect_ports(
        cls, aproxy_redirect_ports: list[str] | str | None
    ) -> list[str]:
        """Parse and validate check_aproxy_redirect_ports config value.

        Args:
            aproxy_redirect_ports: The aproxy_exclude_addresses configuration input.

        Raises:
            CharmConfigInvalidError: invalid check_aproxy_redirect_ports configuration input.

        Returns:
            Parsed check_aproxy_redirect_ports configuration input.
        """
        aproxy_redirect_ports = cls._parse_list(aproxy_redirect_ports)
        result = []
        for port_range in aproxy_redirect_ports:
            if "-" in port_range:
                start, _, end = port_range.partition("-")
                if not start:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_REDIRECT_PORTS_CONFIG_NAME} config, "
                        f"in {repr(port_range)}, missing start in range"
                    )
                if not end:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_REDIRECT_PORTS_CONFIG_NAME} config, "
                        f"in {repr(port_range)}, missing end in range"
                    )
                try:
                    start_num = int(start)
                    end_num = int(end)
                except ValueError as exc:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_REDIRECT_PORTS_CONFIG_NAME} config, "
                        f"in {repr(port_range)}, not a number"
                    ) from exc
                if start_num < 0 or start_num > 65535 or end_num < 0 or end_num > 65535:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_REDIRECT_PORTS_CONFIG_NAME} config, "
                        f"in {repr(port_range)}, invalid port number"
                    )
            else:
                if not port_range.isdecimal() or int(port_range) < 0 or int(port_range) > 65535:
                    raise CharmConfigInvalidError(
                        f"Invalid {APROXY_REDIRECT_PORTS_CONFIG_NAME} config,"
                        f"in {repr(port_range)}, port is not a number or invalid port number"
                    )
            result.append(port_range)
        return result

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

        dockerhub_mirror = cast(str, charm.config.get(DOCKERHUB_MIRROR_CONFIG_NAME, "")) or None
        openstack_clouds_yaml = cls._parse_openstack_clouds_config(charm)

        try:
            labels = _parse_labels(cast(str, charm.config.get(LABELS_CONFIG_NAME, "")))
        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid {LABELS_CONFIG_NAME} config: {exc}") from exc

        manager_proxy_command = (
            cast(str, charm.config.get(MANAGER_SSH_PROXY_COMMAND_CONFIG_NAME, "")) or None
        )
        use_aproxy = cast(bool, charm.config.get(USE_APROXY_CONFIG_NAME, False))

        custom_pre_job_script = (
            cast(str, charm.config.get(CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME, "")) or None
        )

        runner_manager_log_level = cast(
            LogLevel, charm.config.get(RUNNER_MANAGER_LOG_LEVEL_CONFIG_NAME, "INFO")
        )
        # pydantic allows to pass str as AnyHttpUrl, mypy complains about it
        return cls(
            allow_external_contributor=cast(
                bool, charm.config.get(ALLOW_EXTERNAL_CONTRIBUTOR_CONFIG_NAME, False)
            ),
            dockerhub_mirror=dockerhub_mirror,  # type: ignore
            labels=labels,
            openstack_clouds_yaml=openstack_clouds_yaml,
            path=github_config.path if github_config else None,
            reconcile_interval=reconcile_interval,
            token=github_config.token if github_config else None,
            manager_proxy_command=manager_proxy_command,
            use_aproxy=use_aproxy,
            # mypy doesn't know about the validator
            aproxy_exclude_addresses=charm.config.get(  # type: ignore
                APROXY_EXCLUDE_ADDRESSES_CONFIG_NAME
            ),
            aproxy_redirect_ports=charm.config.get(  # type: ignore
                APROXY_REDIRECT_PORTS_CONFIG_NAME
            ),
            custom_pre_job_script=custom_pre_job_script,
            runner_manager_log_level=runner_manager_log_level,
        )


class OpenstackImage(BaseModel):
    """OpenstackImage from image builder relation data.

    Attributes:
        id: The OpenStack image ID.
        tags: Image tags, e.g. jammy
    """

    id: str | None
    tags: list[str] | None

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
        base_virtual_machines: Number of virtual machine-based runners to spawn.
        max_total_virtual_machines: Maximum possible machine number to spawn for the unit in
           for reactive processes.
        flavor_label_combinations: list of FlavorLabel.
        openstack_network: Network on openstack to use for virtual machines.
        openstack_image: Openstack image to use for virtual machines.
    """

    base_virtual_machines: int
    max_total_virtual_machines: int
    flavor_label_combinations: list[FlavorLabel]
    openstack_network: str
    openstack_image: OpenstackImage | None

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
        base_virtual_machines = int(charm.config[BASE_VIRTUAL_MACHINES_CONFIG_NAME])
        max_total_virtual_machines = int(charm.config[MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME])

        # Remove these conditions when "virtual-machines" config option is deleted.
        virtual_machines = int(charm.config[VIRTUAL_MACHINES_CONFIG_NAME])
        if base_virtual_machines == 0 and max_total_virtual_machines == 0:
            base_virtual_machines = virtual_machines
            max_total_virtual_machines = virtual_machines
        elif virtual_machines != 0:
            raise CharmConfigInvalidError(
                "Invalid configuration. "
                "Both deprecated and new configuration are set for the number of machines to spawn."
            )

        flavor_label_config = cast(str, charm.config[FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME])
        flavor_label_combinations = _parse_flavor_label_list(flavor_label_config)
        if len(flavor_label_combinations) == 0:
            flavor = cast(str, charm.config[OPENSTACK_FLAVOR_CONFIG_NAME])
            if not flavor:
                raise CharmConfigInvalidError("OpenStack flavor not specified")
            flavor_label_combinations = [FlavorLabel(flavor, None)]
        elif len(flavor_label_combinations) > 1:
            raise CharmConfigInvalidError("Several flavor-label combinations not yet implemented")
        openstack_network = charm.config[OPENSTACK_NETWORK_CONFIG_NAME]
        openstack_image = OpenstackImage.from_charm(charm)

        return cls(
            base_virtual_machines=base_virtual_machines,
            max_total_virtual_machines=max_total_virtual_machines,
            flavor_label_combinations=flavor_label_combinations,
            openstack_network=cast(str, openstack_network),
            openstack_image=openstack_image,
        )


def build_proxy_config_from_charm() -> "ProxyConfig":
    """Initialize the proxy config from charm.

    Returns:
        Current proxy config of the charm.
    """
    http_proxy = get_env_var("JUJU_CHARM_HTTP_PROXY") or None
    https_proxy = get_env_var("JUJU_CHARM_HTTPS_PROXY") or None
    no_proxy = get_env_var("JUJU_CHARM_NO_PROXY") or None

    # there's no need for no_proxy if there's no http_proxy or https_proxy
    if not (https_proxy or http_proxy) and no_proxy:
        no_proxy = None

    return ProxyConfig(
        http=http_proxy,
        https=https_proxy,
        no_proxy=no_proxy,
    )


def _build_runner_proxy_config_from_charm(charm: CharmBase) -> "ProxyConfig":
    """Initialize the proxy configuration for the runner."""
    runner_http_proxy = cast(str, charm.config.get(RUNNER_HTTP_PROXY_CONFIG_NAME, "")) or None
    if runner_http_proxy:
        return ProxyConfig(
            http=runner_http_proxy,
        )
    return build_proxy_config_from_charm()


def _build_ssh_debug_connection_from_charm(charm: CharmBase) -> list[SSHDebugConnection]:
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
        use_runner_http_proxy = cast(
            bool, charm.config.get(USE_RUNNER_PROXY_FOR_TMATE_CONFIG_NAME, False)
        )
        ssh_debug_connections.append(
            # pydantic allows string to be passed as IPvAnyAddress and as int,
            # mypy complains about it
            SSHDebugConnection(
                host=host,  # type: ignore
                port=port,  # type: ignore
                rsa_fingerprint=rsa_fingerprint,
                ed25519_fingerprint=ed25519_fingerprint,
                use_runner_http_proxy=use_runner_http_proxy,
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


# Charm State is a list of all the configurations and states of the charm and
# has therefore a lot of attributes.
@dataclasses.dataclass(frozen=True)
class CharmState:  # pylint: disable=too-many-instance-attributes
    """The charm state.

    Attributes:
        charm_config: Configuration of the juju charm.
        is_metrics_logging_available: Whether the charm is able to issue metrics.
        proxy_config: Proxy-related configuration.
        runner_proxy_config: Proxy-related configuration for the runner.
        reactive_config: The charm configuration related to reactive spawning mode.
        runner_config: The charm configuration related to runner VM configuration.
        ssh_debug_connections: SSH debug connections configuration information.
    """

    is_metrics_logging_available: bool
    proxy_config: ProxyConfig
    runner_proxy_config: ProxyConfig
    charm_config: CharmConfig
    runner_config: OpenstackRunnerConfig
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
        state_dict["runner_proxy_config"] = json.loads(state_dict["runner_proxy_config"].json())
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
            charm_config = CharmConfig.from_charm(charm)
        except ValueError as exc:
            logger.error("Invalid charm config: %s", exc)
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc

        try:
            proxy_config = build_proxy_config_from_charm()
            runner_proxy_config = _build_runner_proxy_config_from_charm(charm)
            if charm_config.use_aproxy and not runner_proxy_config.proxy_address:
                raise CharmConfigInvalidError(
                    "Invalid proxy configuration: aproxy requires a runner proxy to be set"
                )

        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid proxy configuration: {str(exc)}") from exc

        try:
            runner_config = OpenstackRunnerConfig.from_charm(charm)
        except ValueError as exc:
            raise CharmConfigInvalidError(f"Invalid configuration: {str(exc)}") from exc

        # Remove this code when when several FlavorLabel combinations are supported.
        # There should be one.
        flavor_label_combination = runner_config.flavor_label_combinations[0]
        if flavor_label_combination.label:
            charm_config.labels = (flavor_label_combination.label,) + charm_config.labels

        try:
            ssh_debug_connections = _build_ssh_debug_connection_from_charm(charm)
        except ValidationError as exc:
            logger.error("Invalid SSH debug info: %s.", exc)
            raise CharmConfigInvalidError("Invalid SSH Debug info") from exc

        reactive_config = ReactiveConfig.from_database(database)

        state = cls(
            is_metrics_logging_available=bool(charm.model.relations[COS_AGENT_INTEGRATION_NAME]),
            proxy_config=proxy_config,
            runner_proxy_config=runner_proxy_config,
            charm_config=charm_config,
            runner_config=runner_config,
            reactive_config=reactive_config,
            ssh_debug_connections=ssh_debug_connections,
        )

        cls._store_state(state)

        return state


def _parse_flavor_label_list(flavor_label_config: str) -> list[FlavorLabel]:
    """Parse flavor-label config option."""
    combinations = []

    split_flavor_list = flavor_label_config.split(",")

    # An input like "" will get here.
    if len(split_flavor_list) == 1 and not split_flavor_list[0]:
        return []

    for flavor_label in flavor_label_config.split(","):
        flavor_label_stripped = flavor_label.strip()
        try:
            flavor, label = flavor_label_stripped.split(":")
            if not flavor:
                raise CharmConfigInvalidError("Invalid empty flavor in flavor-label configuration")
            if not label:
                raise CharmConfigInvalidError("Invalid empty label in flavor-label configuration")
            combinations.append(FlavorLabel(flavor, label))
        except ValueError as exc:
            raise CharmConfigInvalidError("Invalid flavor-label configuration") from exc
    return combinations
