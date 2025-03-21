# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base configuration for the Application."""

from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field, IPvAnyAddress, MongoDsn, validator

from . import github


class ApplicationConfiguration(BaseModel):
    """Main entry point for the Application Configuration.

    Attributes:
        name: Name to identify the manager. Used for metrics.
        extra_labels: Extra labels to add to the runner.
        github_config: GitHub configuration.
        service_config: The configuration for supporting services.
        non_reactive_configuration: Configuration for non-reactive mode.
        reactive_configuration: Configuration for reactive mode.
    """

    name: str
    extra_labels: list[str]
    github_config: github.GitHubConfiguration
    service_config: "SupportServiceConfig"
    non_reactive_configuration: "NonReactiveConfiguration"
    reactive_configuration: "ReactiveConfiguration | None"


class SupportServiceConfig(BaseModel):
    """Configuration for supporting services for runners.

    Attributes:
        manager_proxy_command: TODO.
        proxy_config: The proxy configuration.
        runner_proxy_config: TODO.
        dockerhub_mirror: The dockerhub mirror to use for runners.
        ssh_debug_connections: The information on the ssh debug services.
        repo_policy_compliance: The configuration of the repo policy compliance service.
    """

    manager_proxy_command: str | None = None
    proxy_config: "ProxyConfig | None"
    runner_proxy_config: "ProxyConfig | None"
    dockerhub_mirror: str | None
    ssh_debug_connections: "list[SSHDebugConnection]"
    repo_policy_compliance: "RepoPolicyComplianceConfig | None"


class ProxyConfig(BaseModel):
    """Proxy configuration.

    Attributes:
        aproxy_address: The address of aproxy snap instance if use_aproxy is enabled.
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
        use_aproxy: Whether aproxy should be used for the runners.
    """

    http: Optional[AnyHttpUrl]
    https: Optional[AnyHttpUrl]
    no_proxy: Optional[str]
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
            aproxy_address = (
                proxy_address.host
                if not proxy_address.port
                else f"{proxy_address.host}:{proxy_address.port}"
            )
        else:
            aproxy_address = None
        return aproxy_address

    @validator("use_aproxy")
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
        if use_aproxy and not (values.get("http") or values.get("https")):
            raise ValueError("aproxy requires http or https to be set")

        return use_aproxy

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
        use_runner_http_proxy: TODO
    """

    host: IPvAnyAddress
    port: int = Field(0, gt=0, le=65535)
    rsa_fingerprint: str = Field(pattern="^SHA256:.*")
    ed25519_fingerprint: str = Field(pattern="^SHA256:.*")
    use_runner_http_proxy: bool = False


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
