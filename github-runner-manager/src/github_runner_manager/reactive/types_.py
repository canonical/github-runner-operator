#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing reactive scheduling related types."""

from pydantic import BaseModel

from github_runner_manager.configuration.base import QueueConfig
from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManagerConfig,
)


class ReactiveProcessConfig(BaseModel):
    """The configuration for the reactive runner to spawn.

    Attributes:
        queue: The queue configuration.
        manager_name: Name of the manager.
        platform_configuration: Configuration for runner provider platform.
        cloud_runner_manager: The OpenStack runner manager configuration.
        supported_labels: The supported labels for the runner.
        labels: Labels to use for the runners.
    """

    queue: QueueConfig
    manager_name: str
    platform_configuration: GitHubConfiguration | JobManagerConfiguration
    cloud_runner_manager: OpenStackRunnerManagerConfig
    supported_labels: set[str]
    labels: list[str]
