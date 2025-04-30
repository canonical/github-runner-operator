# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base configuration for the Application."""

import logging
from dataclasses import dataclass
from typing import Optional, TextIO

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field, IPvAnyAddress, MongoDsn, root_validator

from github_runner_manager.configuration import github
from github_runner_manager.openstack_cloud.configuration import OpenStackConfiguration

logger = logging.getLogger(__name__)


# The github-runner-manager is being refactor from a library to an application.
# Once the charm no longer rely on the github-runner-manager as a library this will be removed.
# The github-runner-manager needs a input representing the user for process execution due to as a
# library the user needs to be a hardcoded value. With the github-runner-manager as application,
# user would be the current user running the application.
@dataclass
class UserInfo:
    """The user to run the reactive process.

    Attributes:
        user: The user for running the reactive processes.
        group: The user group for running the reactive processes.
    """

    user: str
    group: str


class ApplicationConfiguration(BaseModel):
    """Main entry point for the Application Configuration.

    Attributes:
        name: Name to identify the manager. Used for metrics.
        extra_labels: Extra labels to add to the runner.
        github_config: GitHub configuration.
        service_config: The configuration for supporting services.
        non_reactive_configuration: Configuration for non-reactive mode.
        reactive_configuration: Configuration for reactive mode.
        openstack_configuration: Configuration for authorization to a OpenStack host.
    """

    name: str
    extra_labels: list[str]
    github_config: github.GitHubConfiguration
    service_config: "SupportServiceConfig"
    non_reactive_configuration: "NonReactiveConfiguration"
    reactive_configuration: "ReactiveConfiguration | None"
    openstack_configuration: OpenStackConfiguration

    @staticmethod
    def from_yaml_file(file: TextIO) -> "ApplicationConfiguration":
        """Initialize configuration from a YAML formatted file.

        Args:
            file: The file object to parse the configuration from.

        Returns:
            The configuration.
        """
        config = yaml.safe_load(file)
        return ApplicationConfiguration.validate(config)


class SupportServiceConfig(BaseModel):
    """Configuration for supporting services for runners.

    Attributes:
        manager_proxy_command: ProxyCommand to use for the ssh connection to the runner.
        proxy_config: The proxy configuration.
        runner_proxy_config: The proxy configuration for the runner.
        use_aproxy: Whether aproxy should be used for the runners.
        dockerhub_mirror: The dockerhub mirror to use for runners.
        ssh_debug_connections: The information on the ssh debug services.
        repo_policy_compliance: The configuration of the repo policy compliance service.
    """

    manager_proxy_command: str | None = None
    proxy_config: "ProxyConfig | None"
    runner_proxy_config: "ProxyConfig | None"
    use_aproxy: bool
    dockerhub_mirror: str | None
    ssh_debug_connections: "list[SSHDebugConnection]"
    repo_policy_compliance: "RepoPolicyComplianceConfig | None"

    @root_validator(pre=False, skip_on_failure=True)
    @classmethod
    def check_use_aproxy(cls, values: dict) -> dict:
        """Validate the proxy configuration required if aproxy is enabled.

        Args:
            values: Values in the pydantic model.

        Raises:
            ValueError: if use_aproxy was set but no http/https was passed.

        Returns:
            Values in the pydantic model.
        """
        runner_proxy_enabled = False
        runner_proxy_config = values.get("runner_proxy_config")
        if runner_proxy_config and runner_proxy_config.proxy_address:
            runner_proxy_enabled = True
        if values.get("use_aproxy") and not runner_proxy_enabled:
            raise ValueError("aproxy requires the runner http or https to be set")
        return values


class ProxyConfig(BaseModel):
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
        proxy_address: The address of the proxy.
        proxy_host: The host of the proxy.
        proxy_port: The port of the proxy.
    """

    http: Optional[AnyHttpUrl]
    https: Optional[AnyHttpUrl]
    no_proxy: Optional[str]

    @property
    def proxy_address(self) -> Optional[str]:
        """Return the address of the proxy."""
        proxy = self.http or self.https
        if proxy:
            proxy_address = proxy.host if not proxy.port else f"{proxy.host}:{proxy.port}"
            return proxy_address
        return None

    @property
    def proxy_host(self) -> Optional[str]:
        """Return the host of the proxy."""
        proxy_address = self.http or self.https
        return proxy_address.host if proxy_address else None

    @property
    def proxy_port(self) -> Optional[str]:
        """Return the port of the proxy."""
        proxy_address = self.http or self.https
        return proxy_address.port if proxy_address else None

    def __bool__(self) -> bool:
        """Return whether the proxy config is set.

        Returns:
            Whether the proxy config is set.
        """
        return bool(self.http or self.https)


class SSHDebugConnection(BaseModel):
    """SSH connection information for debug workflow.

    Attributes:
        host: The SSH relay server host IP address inside the VPN.
        port: The SSH relay server port.
        rsa_fingerprint: The host SSH server public RSA key fingerprint.
        ed25519_fingerprint: The host SSH server public ed25519 key fingerprint.
        use_runner_http_proxy: Whether to use runner proxy for the SSH connection.
        local_proxy_host: Local host to use for proxying.
        local_proxy_port: Local port to use for proxying.
    """

    host: IPvAnyAddress
    port: int = Field(0, gt=0, le=65535)
    rsa_fingerprint: str = Field(pattern="^SHA256:.*")
    ed25519_fingerprint: str = Field(pattern="^SHA256:.*")
    use_runner_http_proxy: bool = False
    local_proxy_host: str = "127.0.0.1"
    local_proxy_port: int = 3129


class RepoPolicyComplianceConfig(BaseModel):
    """Configuration for the repo policy compliance service.

    Attributes:
        token: Token for the repo policy compliance service.
        url: URL of the repo policy compliance service.
    """

    token: str
    url: AnyHttpUrl


class NonReactiveConfiguration(BaseModel):
    """Configuration for non-reactive mode.

    Attributes:
        combinations: Different combinations of flavor and image to spawn in non-reactive mode.
    """

    combinations: "list[NonReactiveCombination]"


class NonReactiveCombination(BaseModel):
    """Combination of image and flavor that the application can spawn in non-reactive mode.

    Attributes:
        image: Information about the image to spawn.
        flavor: Information about the flavor to spawn.
        base_virtual_machines: Number of instances to spawn for this combination.
    """

    image: "Image"
    flavor: "Flavor"
    base_virtual_machines: int


class ReactiveConfiguration(BaseModel):
    """Configuration for reactive mode.

    Attributes:
        queue: Queue to listen for reactive requests to spawn runners.
        max_total_virtual_machines: Maximum number of instances to spawn by the application.
           This value will be only checked in reactive mode, and will include all the instances
           (reactive and non-reactive) spawned by the application.
        images: List of valid images to spawn in reactive mode.
        flavors: List of valid flavors to spawn in reactive mode.
    """

    queue: "QueueConfig"
    max_total_virtual_machines: int
    images: "list[Image]"
    flavors: "list[Flavor]"


class QueueConfig(BaseModel):
    """The configuration for the message queue.

    Attributes:
        mongodb_uri: The URI of the MongoDB database.
        queue_name: The name of the queue.
    """

    mongodb_uri: MongoDsn
    queue_name: str


class Image(BaseModel):
    """Information for an image with its associated labels.

    Attributes:
        name: Image name or id.
        labels: List of labels associated to the image.
    """

    name: str
    labels: list[str]


class Flavor(BaseModel):
    """Information for a flavor with its associated labels.

    Attributes:
        name: Flavor name of id.
        labels: List of labels associated to the flavor.
    """

    name: str
    labels: list[str]


# For pydantic to work with forward references.
ApplicationConfiguration.update_forward_refs()
SupportServiceConfig.update_forward_refs()
NonReactiveConfiguration.update_forward_refs()
NonReactiveCombination.update_forward_refs()
ReactiveConfiguration.update_forward_refs()
