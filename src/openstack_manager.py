# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import logging
from dataclasses import dataclass
from pathlib import Path
from subprocess import SubprocessError
from typing import Iterable, Optional

import jinja2
import keystoneauth1.exceptions.http
import openstack
import openstack.compute.v2.server
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
import yaml
from openstack.exceptions import OpenStackCloudException
from openstack.identity.v3.project import Project

from errors import OpenStackInvalidConfigError, OpenStackUnauthorizedError
from github_type import RunnerApplication
from runner_type import GithubPath, ProxySetting
from utilities import execute_command

logger = logging.getLogger(__name__)

CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")
IMAGE_PATH = Path("jammy-server-cloudimg-amd64-compressed.img")
IMAGE_NAME = "github-runner-jammy"
BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"


def _validate_cloud_config(cloud_config: dict) -> None:
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


def _write_config_to_disk(cloud_config: dict) -> None:
    """Write the cloud configuration to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to write to disk.
    """
    CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLOUDS_YAML_PATH.write_text(encoding="utf-8", data=yaml.dump(cloud_config))


def _create_connection(cloud_config: dict) -> openstack.connection.Connection:
    """Create a connection object.

    This method should be called with a valid cloud_config. See def _validate_cloud_config.
    Also, this method assumes that the clouds.yaml exists on CLOUDS_YAML_PATH. See def
    _write_config_to_disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the config has not all required information.

    Returns:
        An openstack.connection.Connection object.
    """
    clouds = list(cloud_config["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
    cloud_name = clouds[0]

    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. Therefore, no catch here.
    return openstack.connect(cloud_name)


def initialize(cloud_config: dict) -> None:
    """Initialize Openstack integration.

    Validates config and writes it to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    _validate_cloud_config(cloud_config)
    _write_config_to_disk(cloud_config)


def list_projects(cloud_config: dict) -> list[Project]:
    """List all projects in the OpenStack cloud.

    The purpose of the method is just to try out openstack integration and
    it may be removed in the future.

    It currently returns objects directly from the sdk,
    which may not be ideal (mapping to domain objects may be preferable).

    Returns:
        A list of projects.
    """
    conn = _create_connection(cloud_config)
    try:
        projects = conn.list_projects()
        logger.debug("OpenStack connection successful.")
        logger.debug("Projects: %s", projects)
        # pylint thinks this isn't an exception
    except keystoneauth1.exceptions.http.Unauthorized as exc:
        raise OpenStackUnauthorizedError(  # pylint: disable=bad-exception-cause
            "Unauthorized to connect to OpenStack."
        ) from exc

    return projects


class ImageBuildError(Exception):
    """Exception representing an error during image build process."""


def _build_image_command(
    runner_info: RunnerApplication, proxies: Optional[ProxySetting] = None
) -> list[str]:
    """Get command for building runner image.

    Returns:
        Command to execute to build runner image.
    """
    if not proxies:
        proxies = ProxySetting()

    http_proxy = proxies.get("http", "")
    https_proxy = proxies.get("https", "")
    no_proxy = proxies.get("no_proxy", "")

    cmd = [
        "/usr/bin/bash",
        BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME,
        runner_info["download_url"],
        http_proxy,
        https_proxy,
        no_proxy,
    ]

    return cmd


@dataclass
class InstanceConfig:
    """The configuration values for creating a single runner instance.

    Args:
        name: Name of the image to launch the GitHub runner instance with.
        labels: The runner instance labels.
        registration_token: Token for registering the runner on GitHub.
        github_path: The GitHub repo/org path
        image: The Openstack image to use to boot the instance with.
    """

    name: str
    labels: Iterable[str]
    registration_token: str
    github_path: GithubPath
    image: str


def build_image(
    cloud_config: dict,
    runner_info: RunnerApplication,
    proxies: Optional[ProxySetting] = None,
) -> openstack.image.v2.image.Image:
    """Build and upload an image to OpenStack.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        runner_info: The runner application metadata.
        proxies: HTTP proxy settings.

    Raises:
        ImageBuildError: If there were errors buliding/creating the image.

    Returns:
        The OpenStack image object.
    """
    try:
        execute_command(_build_image_command(runner_info, proxies), check_exit=True)
    except SubprocessError as exc:
        raise ImageBuildError("Failed to build image.") from exc

    try:
        conn = _create_connection(cloud_config)
        return conn.create_image(name=IMAGE_NAME, filename=IMAGE_PATH)
    except OpenStackCloudException as exc:
        raise ImageBuildError("Failed to upload image.") from exc


class InstanceLaunchError(Exception):
    """Exception representing an error during instance launch process."""


def create_instance(
    cloud_config: dict,
    instance_config: InstanceConfig,
) -> openstack.compute.v2.server.Server:
    """Create an OpenStack instance.

    Args:
        cloud_config: The cloud configuration to connect Openstack with.
        instance_config: The configuration values for Openstack instance to launch.

    Raises:
        InstanceLaunchError: if any errors occurred while launching Openstack instance.

    Returns:
        The created server.
    """
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)
    cloud_userdata = environment.get_template("openstack-userdata.sh.j2").render(
        github_url=f"https://github.com/{instance_config.github_path.path()}",
        token=instance_config.registration_token,
        instance_labels=",".join(instance_config.labels),
        instance_name=instance_config.name,
    )

    try:
        conn = _create_connection(cloud_config)
        return conn.create_server(
            name="test",
            image=instance_config.image,
            flavor="m1.tiny",
            userdata=cloud_userdata,
            key_name="sunbeam",
            security_groups=["default"],
            admin_pass="helloworld",
            ip_pool=["external-network"],
        )
    except OpenStackCloudException as exc:
        raise InstanceLaunchError("Failed to launch instance.") from exc
