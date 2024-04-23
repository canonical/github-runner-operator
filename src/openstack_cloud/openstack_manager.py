# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import json
import logging
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Iterable, Literal, NamedTuple, Optional

import jinja2
import openstack
import openstack.compute.v2.server
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
from openstack.exceptions import OpenStackCloudException

from charm_state import (
    Arch,
    BaseImage,
    ProxyConfig,
    SSHDebugConnection,
    UnsupportedArchitectureError,
)
from errors import (
    OpenstackImageBuildError,
    OpenstackInstanceLaunchError,
    OpenStackUnauthorizedError,
    RunnerBinaryError,
    SubprocessError,
)
from github_client import GithubClient
from github_type import RunnerApplication
from runner_type import GithubPath
from utilities import execute_command, retry

logger = logging.getLogger(__name__)

IMAGE_PATH_TMPL = "{base_image}-server-cloudimg-{architecture}-compressed.img"
# Update the version when the image are modified.
IMAGE_NAME_TMPL = "github-runner-{base_image}-v1"
BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"


@contextmanager
def _create_connection(
    cloud_config: dict[str, dict]
) -> Generator[openstack.connection.Connection, None, None]:
    """Create a connection context managed object, to be used within with statements.

    This method should be called with a valid cloud_config. See _validate_cloud_config.
    Also, this method assumes that the clouds.yaml exists on ~/.config/openstack/clouds.yaml.
    See charm_state.py _write_openstack_config_to_disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        OpenStackUnauthorizedError: if the credentials provided is not authorized.

    Yields:
        An openstack.connection.Connection object.
    """
    clouds = list(cloud_config["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
    cloud_name = clouds[0]

    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. Therefore, no catch here for such exception.
    try:
        with openstack.connect(cloud=cloud_name) as conn:
            conn.authorize()
            yield conn
    # pylint thinks this isn't an exception, but does inherit from Exception class.
    except openstack.exceptions.HttpException as exc:  # pylint: disable=bad-exception-cause
        raise OpenStackUnauthorizedError("Unauthorized credentials.") from exc


class ProxyStringValues(NamedTuple):
    """Wrapper class to proxy values to string.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
    """

    http: str
    https: str
    no_proxy: str


def _get_default_proxy_values(proxies: Optional[ProxyConfig] = None) -> ProxyStringValues:
    """Get default proxy string values, empty string if None.

    Used to parse proxy values for file configurations, empty strings if None.

    Args:
        proxies: The proxy configuration information.

    Returns:
        Proxy strings if set, empty string otherwise.
    """
    if not proxies:
        return ProxyStringValues(http="", https="", no_proxy="")
    return ProxyStringValues(
        http=str(proxies.http or ""),
        https=str(proxies.https or ""),
        no_proxy=proxies.no_proxy or "",
    )


def _generate_docker_proxy_unit_file(proxies: Optional[ProxyConfig] = None) -> str:
    """Generate docker proxy systemd unit file.

    Args:
        proxies: HTTP proxy settings.

    Returns:
        Contents of systemd-docker-proxy unit file.
    """
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)
    return environment.get_template("systemd-docker-proxy.j2").render(proxies=proxies)


def _generate_docker_client_proxy_config_json(
    http_proxy: str, https_proxy: str, no_proxy: str
) -> str:
    """Generate proxy config.json for docker client.

    Args:
        http_proxy: HTTP proxy URL.
        https_proxy: HTTPS proxy URL.
        no_proxy: URLs to not proxy through.

    Returns:
        Contents of docker config.json file.
    """
    return json.dumps(
        {
            "proxies": {
                "default": {
                    key: value
                    for key, value in (
                        ("httpProxy", http_proxy),
                        ("httpsProxy", https_proxy),
                        ("noProxy", no_proxy),
                    )
                    if value
                }
            }
        },
        indent=4,
    )


def _build_image_command(
    runner_info: RunnerApplication,
    base_image: BaseImage,
    proxies: Optional[ProxyConfig] = None,
) -> list[str]:
    """Get command for building runner image.

    Args:
        runner_info: The runner application to fetch runner tar download url.
        base_image: The ubuntu base image to use.
        proxies: HTTP proxy settings.

    Returns:
        Command to execute to build runner image.
    """
    docker_proxy_service_conf_content = _generate_docker_proxy_unit_file(proxies=proxies)

    proxy_values = _get_default_proxy_values(proxies=proxies)

    docker_client_proxy_content = _generate_docker_client_proxy_config_json(
        http_proxy=proxy_values.http,
        https_proxy=proxy_values.https,
        no_proxy=proxy_values.no_proxy,
    )

    cmd = [
        "/usr/bin/bash",
        BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME,
        runner_info["download_url"],
        proxy_values.http,
        proxy_values.https,
        proxy_values.no_proxy,
        docker_proxy_service_conf_content,
        docker_client_proxy_content,
        str(base_image),
    ]

    return cmd


@dataclass
class InstanceConfig:
    """The configuration values for creating a single runner instance.

    Attributes:
        name: Name of the image to launch the GitHub runner instance with.
        labels: The runner instance labels.
        registration_token: Token for registering the runner on GitHub.
        github_path: The GitHub repo/org path
        openstack_image_id: The Openstack image id to use to boot the instance with.
        base_image: The ubuntu image to use as image build base.
    """

    name: str
    labels: Iterable[str]
    registration_token: str
    github_path: GithubPath
    openstack_image_id: str
    base_image: BaseImage


SupportedCloudImageArch = Literal["amd64", "arm64"]


def _get_supported_runner_arch(arch: str) -> SupportedCloudImageArch:
    """Validate and return supported runner architecture.

    The supported runner architecture takes in arch value from Github supported architecture and
    outputs architectures supported by ubuntu cloud images.
    See: https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners\
/about-self-hosted-runners#architectures
    and https://cloud-images.ubuntu.com/jammy/current/

    Args:
        arch: The compute architecture to check support for.

    Raises:
        UnsupportedArchitectureError: If an unsupported architecture was passed.

    Returns:
        The supported architecture.
    """
    match arch:
        case Arch.X64:
            return "amd64"
        case Arch.ARM64:
            return "arm64"
        case _:
            raise UnsupportedArchitectureError(arch)


@dataclass
class BuildImageConfig:
    """The configuration values for building openstack image.

    Attributes:
        arch: The image architecture to build for.
        base_image: The ubuntu image to use as image build base.
        proxies: HTTP proxy settings.
    """

    arch: Arch
    base_image: BaseImage
    proxies: Optional[ProxyConfig] = None


class ImageDeleteError(Exception):
    """Represents an error while deleting existing openstack image."""


def _put_image(
    cloud_config: dict[str, dict], image_arch: SupportedCloudImageArch, base_image: BaseImage
) -> str:
    """Create or replace the image with existing name.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        image_arch: Ubuntu cloud image architecture.
        base_image: The ubuntu base image to use.

    Raises:
        ImageDeleteError: If there was an error deleting the image.
        OpenStackCloudException: If there was an error communicating with the Openstack API.

    Returns:
        The ID of the image created.
    """
    try:
        with _create_connection(cloud_config) as conn:
            existing_image: openstack.image.v2.image.Image
            for existing_image in conn.search_images(
                name_or_id=IMAGE_NAME_TMPL.format(base_image=base_image)
            ):
                # images with same name (different ID) can be created and will error during server
                # instantiation.
                if not conn.delete_image(name_or_id=existing_image.id, wait=True):
                    raise ImageDeleteError("Failed to delete duplicate image on Openstack.")
            image: openstack.image.v2.image.Image = conn.create_image(
                name=IMAGE_NAME_TMPL.format(base_image=base_image.value),
                filename=IMAGE_PATH_TMPL.format(
                    architecture=image_arch, base_image=base_image.value
                ),
                wait=True,
            )
            return image.id
    # 2024/04/02 - We should define a new error, wrap it and re-raise it.
    except OpenStackCloudException:  # pylint: disable=try-except-raise
        raise


def build_image(
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubPath,
    config: BuildImageConfig,
) -> str:
    """Build and upload an image to OpenStack.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        github_client: The Github client to interact with Github API.
        path: Github organisation or repository path.
        config: The image build configuration values.

    Raises:
        OpenstackImageBuildError: If there were errors building/creating the image.

    Returns:
        The created OpenStack image id.
    """
    try:
        runner_application = github_client.get_runner_application(path=path, arch=config.arch)
    except RunnerBinaryError as exc:
        raise OpenstackImageBuildError("Failed to fetch runner application.") from exc

    try:
        execute_command(
            _build_image_command(runner_application, config.base_image, config.proxies),
            check_exit=True,
        )
    except SubprocessError as exc:
        raise OpenstackImageBuildError("Failed to build image.") from exc

    runner_arch = runner_application["architecture"]
    try:
        image_arch = _get_supported_runner_arch(arch=config.arch)
    except UnsupportedArchitectureError as exc:
        raise OpenstackImageBuildError(f"Unsupported architecture {runner_arch}") from exc

    try:
        return _put_image(
            cloud_config=cloud_config, image_arch=image_arch, base_image=config.base_image
        )
    except (ImageDeleteError, OpenStackCloudException) as exc:
        raise OpenstackImageBuildError(f"Failed to upload image: {str(exc)}") from exc


def create_instance_config(
    unit_name: str,
    openstack_image_id: str,
    path: GithubPath,
    github_client: GithubClient,
    base_image: BaseImage,
) -> InstanceConfig:
    """Create an instance config from charm data.

    Args:
        unit_name: The charm unit name.
        openstack_image_id: The openstack image id to create the instance with.
        path: Github organisation or repository path.
        github_client: The Github client to interact with Github API.
        base_image: The ubuntu base image to use.

    Returns:
        Instance configuration created.
    """
    app_name, unit_num = unit_name.rsplit("/", 1)
    suffix = secrets.token_hex(12)
    registration_token = github_client.get_runner_registration_token(path=path)
    return InstanceConfig(
        name=f"{app_name}-{unit_num}-{suffix}",
        labels=(app_name, base_image.value),
        registration_token=registration_token,
        github_path=path,
        openstack_image_id=openstack_image_id,
        base_image=base_image,
    )


def _generate_runner_env(
    templates_env: jinja2.Environment,
    proxies: Optional[ProxyConfig] = None,
    dockerhub_mirror: Optional[str] = None,
    ssh_debug_connections: list[SSHDebugConnection] | None = None,
) -> str:
    """Generate Github runner .env file contents.

    Args:
        templates_env: The jinja template environment.
        proxies: Proxy values to enable on the Github runner.
        dockerhub_mirror: The url to Dockerhub to reduce rate limiting.
        ssh_debug_connections: Tmate SSH debug connection information to load as environment vars.

    Returns:
        The .env contents to be loaded by Github runner.
    """
    return templates_env.get_template("env.j2").render(
        proxies=proxies,
        pre_job_script="",
        dockerhub_mirror=dockerhub_mirror or "",
        ssh_debug_info=(secrets.choice(ssh_debug_connections) if ssh_debug_connections else None),
    )


def _generate_cloud_init_userdata(
    templates_env: jinja2.Environment, instance_config: InstanceConfig, runner_env: str
) -> str:
    """Generate cloud init userdata to launch at startup.

    Args:
        templates_env: The jinja template environment.
        instance_config: The configuration values for Openstack instance to launch.
        runner_env: The contents of .env to source when launching Github runner.

    Returns:
        The cloud init userdata script.
    """
    return templates_env.get_template("openstack-userdata.sh.j2").render(
        github_url=f"https://github.com/{instance_config.github_path.path()}",
        token=instance_config.registration_token,
        instance_labels=",".join(instance_config.labels),
        instance_name=instance_config.name,
        env_contents=runner_env,
    )


@retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
def create_instance(
    cloud_config: dict[str, dict],
    instance_config: InstanceConfig,
    proxies: Optional[ProxyConfig] = None,
    dockerhub_mirror: Optional[str] = None,
    ssh_debug_connections: list[SSHDebugConnection] | None = None,
) -> None:
    """Create an OpenStack instance.

    Args:
        cloud_config: The cloud configuration to connect Openstack with.
        instance_config: The configuration values for Openstack instance to launch.
        proxies: HTTP proxy settings.
        dockerhub_mirror:
        ssh_debug_connections:

    Raises:
        OpenstackInstanceLaunchError: if any errors occurred while launching Openstack instance.
    """
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)

    env_contents = _generate_runner_env(
        templates_env=environment,
        proxies=proxies,
        dockerhub_mirror=dockerhub_mirror,
        ssh_debug_connections=ssh_debug_connections,
    )
    cloud_userdata = _generate_cloud_init_userdata(
        templates_env=environment, instance_config=instance_config, runner_env=env_contents
    )

    with _create_connection(cloud_config) as conn:
        try:
            conn.create_server(
                name=instance_config.name,
                image=instance_config.openstack_image_id,
                flavor="m1.small",
                network="demo-network",
                userdata=cloud_userdata,
                wait=True,
                timeout=1200,
            )
        except OpenStackCloudException as exc:
            if not conn.delete_server(instance_config.name):
                logger.error("Failed to delete server %s", instance_config.name)
            raise OpenstackInstanceLaunchError("Failed to launch instance.") from exc
