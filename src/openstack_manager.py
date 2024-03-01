# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import logging
import secrets
from dataclasses import dataclass

# subprocess module is used to call image build script.
from subprocess import SubprocessError  # nosec
from typing import Iterable, Optional

import jinja2
import keystoneauth1.exceptions.http
import openstack
import openstack.compute.v2.server
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
from openstack.exceptions import OpenStackCloudException
from openstack.identity.v3.project import Project

from charm_state import Arch, ProxyConfig
from errors import OpenStackUnauthorizedError, RunnerBinaryError
from github_client import GithubClient
from github_type import RunnerApplication
from runner_type import GithubPath
from utilities import execute_command

logger = logging.getLogger(__name__)

IMAGE_PATH_TMPL = "jammy-server-cloudimg-{architecture}-compressed.img"
IMAGE_NAME = "jammy"
BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"


def _create_connection(cloud_config: dict[str, dict]) -> openstack.connection.Connection:
    """Create a connection object.

    This method should be called with a valid cloud_config. See def _validate_cloud_config.
    Also, this method assumes that the clouds.yaml exists on ~/.config/openstack/clouds.yaml.
    See charm_state.py _write_openstack_config_to_disk.

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


def list_projects(cloud_config: dict[str, dict]) -> list[Project]:
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


def _build_image_command(runner_info: RunnerApplication, proxies: ProxyConfig) -> list[str]:
    """Get command for building runner image.

    Returns:
        Command to execute to build runner image.
    """
    http_proxy = proxies.http or ""
    https_proxy = proxies.https or ""
    no_proxy = proxies.no_proxy or ""

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
        openstack_image: The Openstack image to use to boot the instance with.
    """

    name: str
    labels: Iterable[str]
    registration_token: str
    github_path: GithubPath
    openstack_image: openstack.image.v2.image.Image


def build_image(
    arch: Arch,
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubPath,
    proxies: Optional[ProxyConfig] = None,
) -> openstack.image.v2.image.Image:
    """Build and upload an image to OpenStack.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        github_client: The Github client to interact with Github API.
        path: Github organisation or repository path.
        proxies: HTTP proxy settings.

    Raises:
        ImageBuildError: If there were errors building/creating the image.

    Returns:
        The OpenStack image object.
    """
    try:
        runner_application = github_client.get_runner_application(path=path, arch=arch)
    except RunnerBinaryError as exc:
        raise ImageBuildError("Failed to fetch image.") from exc

    try:
        execute_command(_build_image_command(runner_application, proxies), check_exit=True)
    except SubprocessError as exc:
        raise ImageBuildError("Failed to build image.") from exc

    try:
        conn = _create_connection(cloud_config)
        arch = "amd64" if runner_application["architecture"] == "x64" else "arm64"
        return conn.create_image(
            name=IMAGE_NAME, filename=IMAGE_PATH_TMPL.format(architecture=arch)
        )
    except OpenStackCloudException as exc:
        raise ImageBuildError("Failed to upload image.") from exc


def create_instance_config(
    unit_name: str,
    openstack_image: openstack.image.v2.image.Image,
    path: GithubPath,
    github_client: GithubClient,
) -> InstanceConfig:
    """Create an instance config from charm data.

    Args:
        unit_name: The charm unit name.
        image: Ubuntu image flavor.
        path: Github organisation or repository path.
        github_client: The Github client to interact with Github API.
    """
    app_name, unit_num = unit_name.rsplit("/", 1)
    suffix = secrets.token_hex(12)
    registration_token = github_client.get_runner_registration_token(path=path)
    return InstanceConfig(
        name=f"{app_name}-{unit_num}-{suffix}",
        labels=(app_name, "jammy"),
        registration_token=registration_token,
        github_path=path,
        openstack_image=openstack_image,
    )


class InstanceLaunchError(Exception):
    """Exception representing an error during instance launch process."""


def create_instance(
    cloud_config: dict[str, dict],
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
            name=instance_config.name,
            image=instance_config.openstack_image,
            flavor="m1.tiny",
            userdata=cloud_userdata,
        )
    except OpenStackCloudException as exc:
        raise InstanceLaunchError("Failed to launch instance.") from exc
