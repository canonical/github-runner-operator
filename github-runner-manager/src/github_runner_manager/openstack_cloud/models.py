# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing OpenStack models."""

from dataclasses import dataclass

from github_runner_manager.configuration import SupportServiceConfig
from github_runner_manager.openstack_cloud.configuration import OpenStackCredentials


@dataclass
class OpenStackServerConfig:
    """Configuration for OpenStack server.

    Attributes:
        image: The image name for runners to use.
        flavor: The flavor name for runners to use.
        network: The network name for runners to use.
    """

    image: str
    flavor: str
    network: str


@dataclass
class OpenStackRunnerManagerConfig:
    """Configuration for OpenStack runner manager.

    Attributes:
        allow_external_contributor: Whether to allow runs from forked repository from an external
            contributor.
        prefix: The prefix of the runner names.
        credentials: The OpenStack authorization information.
        server_config: The configuration for OpenStack server.
        service_config: The configuration for supporting services.
    """

    allow_external_contributor: bool
    prefix: str
    credentials: OpenStackCredentials
    server_config: OpenStackServerConfig | None
    service_config: SupportServiceConfig
