# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The configuration file processing for the CLI."""

from typing import TextIO
import typing
import pydantic
import yaml


class Configuration(pydantic.BaseModel):
    """Configuration for github-runner-manager application.

    Attributes:
        name: A name for this github-runner-manager instance.
        github_path: The GitHub path to register the runners.
        github_token: The GitHub Personal Access Token (PAT) to register the runners.
        github_runner_group: The runner group to register runners for GitHub organization. Ignored
            if the runner is registered to GitHub repository. Defaults to None.
        runner_count: The desired number of self-hosted runners.
        runner_labels: The labels 
        openstack_auth_url: The address of the openstack host.
        openstack_project_name: The openstack project name.
        openstack_username: The username for login to the openstack project.
        openstack_password: The password for login to the openstack project.
        openstack_user_domain_name: The domain name for the openstack user.
        openstack_domain_name: The domain name for the openstack project.
        openstack_flavor: The openstack flavor to spawn virtual machine for runners.
        openstack_network: The openstack network to spawn virtual machine for runners.
        dockerhub_mirror: The optional docker registry as dockerhub mirror for the runners to use. 
            Defaults to None.
        repo_policy_compliance_url: The optional repo-policy-compliance address. Defaults to None.
        repo_policy_compliance_token: The token to query the repo-policy-compliance. Defaults to 
            None.
        enable_aproxy: Whether to use aproxy for automatic redirect traffic to HTTP(S) proxy. 
            Defaults to True.
    """
    name: str = pydantic.Field(min_length=1, max_length=50)
    github_path: str = pydantic.Field(min_length=1)
    github_token: str = pydantic.Field(min_length=1)
    github_runner_group: str | None
    runner_count: int = pydantic.Field(ge=0)
    runner_labels: tuple[typing.Annotated[str, pydantic.Field(min_length=1)], ...]
    openstack_auth_url: str = pydantic.Field(min_length=1)
    openstack_project_name: str = pydantic.Field(min_length=1)
    openstack_username: str = pydantic.Field(min_length=1)
    openstack_password: str = pydantic.Field(min_length=1)
    openstack_user_domain_name: str = pydantic.Field(min_length=1)
    openstack_domain_name: str = pydantic.Field(min_length=1)
    openstack_flavor: str = pydantic.Field(min_length=1)
    openstack_network: str = pydantic.Field(min_length=1)
    dockerhub_mirror: str | None = None
    repo_policy_compliance_url: str | None = pydantic.Field(None, min_length=1)
    repo_policy_compliance_token: str | None = pydantic.Field(None, min_length=1)
    enable_aproxy: bool = True

    def from_yaml_file(file: TextIO) -> "Configuration":
        """Initialize configuration from a YAML formatted file.

        Args:
            file: The file object to parse the configuration from.

        Returns:
            The configuration.
        """
        config = yaml.safe_load(file)
        return Configuration(**config)
