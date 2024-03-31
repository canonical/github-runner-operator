# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import json
import logging
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, Literal, NamedTuple, Optional

import jinja2
import openstack
import openstack.compute.v2.server
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
from fabric import Connection as SshConnection
from openstack.connection import Connection as OpenstackConnection
from openstack.exceptions import OpenStackCloudException

from charm_state import Arch, ProxyConfig, SSHDebugConnection, UnsupportedArchitectureError
from errors import (
    OpenstackImageBuildError,
    OpenstackInstanceLaunchError,
    OpenStackUnauthorizedError,
    RunnerBinaryError,
    SubprocessError,
)
from github_client import GithubClient
from github_type import GitHubRunnerStatus, RunnerApplication, SelfHostedRunner
from runner_manager_type import OpenstackRunnerManagerConfig
from runner_type import GithubPath, RunnerByHealth, RunnerGithubInfo
from utilities import execute_command, retry

logger = logging.getLogger(__name__)

IMAGE_PATH_TMPL = "jammy-server-cloudimg-{architecture}-compressed.img"
IMAGE_NAME = "jammy"
SECURITY_GROUP_NAME = "runner-policy"
BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"
_SSH_KEY_PATH = Path("/home/ubuntu/.ssh")


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

    Returns:
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


def _generate_docker_client_proxy_config_json(http_proxy: str, https_proxy: str, no_proxy: str):
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
        }
    )


def _build_image_command(
    runner_info: RunnerApplication, proxies: Optional[ProxyConfig] = None
) -> list[str]:
    """Get command for building runner image.

    Args:
        runner_info: The runner application to fetch runner tar download url.
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
    openstack_image: str


def _get_supported_runner_arch(arch: str) -> Literal["amd64", "arm64"]:
    """Validate and return supported runner architecture.

    The supported runner architecture takes in arch value from Github supported architecture and
    outputs architectures supported by ubuntu cloud images.
    See: https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners\
/about-self-hosted-runners#architectures
    and https://cloud-images.ubuntu.com/jammy/current/

    Args:
        arch: str

    Raises:
        UnsupportedArchitectureError: If an unsupported architecture was passed.

    Returns:
        The supported architecture.
    """
    match arch:
        case "x64":
            return "amd64"
        case "arm64":
            return "arm64"
        case _:
            raise UnsupportedArchitectureError(arch)


def build_image(
    arch: Arch,
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubPath,
    proxies: Optional[ProxyConfig] = None,
) -> str:
    """Build and upload an image to OpenStack.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        github_client: The Github client to interact with Github API.
        path: Github organisation or repository path.
        proxies: HTTP proxy settings.

    Raises:
        ImageBuildError: If there were errors building/creating the image.

    Returns:
        The created OpenStack image id.
    """
    try:
        runner_application = github_client.get_runner_application(path=path, arch=arch)
    except RunnerBinaryError as exc:
        raise OpenstackImageBuildError("Failed to fetch runner application.") from exc

    try:
        execute_command(_build_image_command(runner_application, proxies), check_exit=True)
    except SubprocessError as exc:
        raise OpenstackImageBuildError("Failed to build image.") from exc

    try:
        runner_arch = runner_application["architecture"]
        image_arch = _get_supported_runner_arch(arch=runner_arch)
    except UnsupportedArchitectureError as exc:
        raise OpenstackImageBuildError(f"Unsupported architecture {runner_arch}") from exc

    try:
        with _create_connection(cloud_config) as conn:
            existing_image: openstack.image.v2.image.Image
            for existing_image in conn.search_images(name_or_id=IMAGE_NAME):
                # images with same name (different ID) can be created and will error during server
                # instantiation.
                if not conn.delete_image(name_or_id=existing_image.id, wait=True):
                    raise OpenstackImageBuildError(
                        "Failed to delete duplicate image on Openstack."
                    )
            image: openstack.image.v2.image.Image = conn.create_image(
                name=IMAGE_NAME,
                filename=IMAGE_PATH_TMPL.format(architecture=image_arch),
                wait=True,
            )
            return image.id
    except OpenStackCloudException as exc:
        raise OpenstackImageBuildError("Failed to upload image.") from exc


def create_instance_config(
    app_name: str,
    unit_num: int,
    openstack_image: str,
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
    suffix = secrets.token_hex(12)
    registration_token = github_client.get_runner_registration_token(path=path)
    return InstanceConfig(
        name=f"{app_name}-{unit_num}-{suffix}",
        labels=(app_name, "jammy"),
        registration_token=registration_token,
        github_path=path,
        openstack_image=openstack_image,
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

    try:
        with _create_connection(cloud_config) as conn:
            conn.create_server(
                name=instance_config.name,
                image=instance_config.openstack_image,
                flavor="m1.small",
                userdata=cloud_userdata,
                wait=True,
            )
    except OpenStackCloudException as exc:
        raise OpenstackInstanceLaunchError("Failed to launch instance.") from exc


class OpenstackRunnerManager:
    """Runner manager for OpenStack-based instances.

    Attributes:
        app_name: An name for the set of runners.
        unit: Unit number of the set of runners.
        instance_name: Prefix of the name for the set of runners.
        flavor: OpenStack flavor for defining the runner resources.
        network: OpenStack network for runner network access.
    """

    def __init__(
        self,
        app_name: str,
        unit_num: int,
        openstack_runner_manager_config: OpenstackRunnerManagerConfig,
        cloud_config: dict[str, dict],
    ):
        """Construct OpenstackRunnerManager object.

        Args:
            app_name: An name for the set of runners.
            unit: Unit number of the set of runners.
            openstack_runner_manager_config: Configurations related to runner manager.
            cloud_config: The openstack clouds.yaml in dict format.
        """
        self.app_name = app_name
        self.unit_num = unit_num
        self.instance_name = f"{app_name}-{unit_num}"
        self._config = openstack_runner_manager_config
        self._cloud_config = cloud_config
        self._github = GithubClient(token=self._config.token)

    def get_key_path(self, name: str) -> Path:
        """Get the filepath for storing private SSH of a runner.

        Args:
            name: The name of the runner.
        """
        return _SSH_KEY_PATH / f"runner-{name}.key"

    def _ensure_security_group(self, conn: OpenstackConnection):
        """Ensure runner security group exists.

        Args:
            conn: The connection object to access OpenStack cloud.
        """
        rule_exists_icmp = False
        rule_exists_ssh = False

        existing_security_group = conn.get_security_group(name_or_id=SECURITY_GROUP_NAME)
        if existing_security_group is None:
            logger.info("Security group %s not found, creating it", SECURITY_GROUP_NAME)
            conn.create_security_group(
                name=SECURITY_GROUP_NAME, description="For GitHub self-hosted runners."
            )
        else:
            existing_rules = existing_security_group["security_group_rules"]
            for rule in existing_rules:
                if rule["protocol"] == "icmp":
                    logger.debug(
                        "Found ICMP rule in existing security group %s", SECURITY_GROUP_NAME
                    )
                    rule_exists_icmp = True
                if (
                    rule["protocol"] == "tcp"
                    and rule["port_range_min"] == rule["port_range_max"] == 22
                ):
                    logger.debug(
                        "Found SSH rule in existing security group %s", SECURITY_GROUP_NAME
                    )
                    rule_exists_ssh = True

        if not rule_exists_icmp:
            conn.create_security_group_rule(
                secgroup_name_or_id=SECURITY_GROUP_NAME,
                protocol="icmp",
                direction="ingress",
                ethertype="IPv4",
            )
        if not rule_exists_ssh:
            conn.create_security_group_rule(
                secgroup_name_or_id=SECURITY_GROUP_NAME,
                port_range_min="22",
                port_range_max="22",
                protocol="tcp",
                direction="ingress",
                ethertype="IPv4",
            )

    def _setup_runner_keypair(self, conn: OpenstackConnection, name: str):
        """Set up the SSH keypair for a runner.

        Args:
            conn: The connection object to access OpenStack cloud.
            name: The name of the runner.
        """
        private_key_path = self.get_key_path(name)

        if private_key_path.exists():
            logger.warning("Existing private key file for %s found, removing it.", name)
            private_key_path.unlink()

        keypair = conn.create_keypair(name=name)
        private_key_path.write_text(keypair.private_key)

    def _create_runner(self, conn: OpenstackConnection) -> None:
        """Create a runner on OpenStack cloud.

        Args:
            conn: The connection object to access OpenStack cloud.
        """
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True
        )

        env_contents = _generate_runner_env(
            templates_env=environment,
            proxies=self._config.charm_state.proxy_config,
            dockerhub_mirror=self._config.dockerhub_mirror,
            ssh_debug_connections=self._config.charm_state.ssh_debug_connections,
        )
        instance_config = create_instance_config(
            self.app_name, self.unit_num, IMAGE_NAME, self._config.path, self._github
        )
        cloud_userdata = _generate_cloud_init_userdata(
            templates_env=environment, instance_config=instance_config, runner_env=env_contents
        )

        self._ensure_security_group(conn)
        self._setup_runner_keypair(conn, instance_config.name)
        conn.create_server(
            name=instance_config.name,
            image=IMAGE_NAME,
            flavor=self._config.flavor,
            ip_pool="default",
            network=self._config.network,
            security_groups=["default", SECURITY_GROUP_NAME],
            userdata=cloud_userdata,
            wait=True,
        )

    def get_github_runner_info(self) -> tuple[RunnerGithubInfo]:
        """Get information on GitHub for the runners.

        Returns:
            Collection of runner GitHub information.
        """
        remote_runners_list: list[SelfHostedRunner] = self._github.get_runner_github_info(
            self._config.path
        )
        logger.debug("List of runners found on GitHub:%s", remote_runners_list)
        return tuple(
            RunnerGithubInfo(
                runner.name, runner.id, runner.status == GitHubRunnerStatus.ONLINE, runner.busy
            )
            for runner in remote_runners_list
            if runner.name.startswith(f"{self.instance_name}-")
        )

    def _get_openstack_runner_status(self, conn: OpenstackConnection) -> RunnerByHealth:
        """Get status on OpenStack of each runner.

        Args:
            conn: The connection object to access OpenStack cloud.

        Returns:
            Runner status grouped by health.
        """
        healthy_runner = []
        unhealthy_runner = []
        openstack_instances = [
            instance
            for instance in conn.list_servers()
            if instance.name.startswith(f"{self.instance_name}-")
        ]

        for instance in openstack_instances:
            healthy = False
            for address in instance.addresses[self._config.network]:
                ip = address["addr"]
                ssh_conn = SshConnection(
                    host=ip,
                    user="ubuntu",
                    connect_kwargs={"key_filename": str(self.get_key_path(instance.name))},
                )

                result = ssh_conn.run("ps aux")
                if not result.ok:
                    continue
                if "openstack-userdata.sh" in result.stdout:
                    healthy = True
            if healthy:
                healthy_runner.append(instance.name)
            else:
                unhealthy_runner.append(instance.name)

        return RunnerByHealth(healthy=tuple(healthy_runner), unhealthy=tuple(unhealthy_runner))

    def _remove_runners(self):
        """Remove runners."""
        raise NotImplementedError()

    def reconcile(self, quantity: int) -> int:
        """Reconcile the quantity of runners.

        Args:
            quantity: The number of intended runners.

        Returns:
            The change in number of runners.
        """
        github_info = self.get_github_runner_info()
        online_runners = [runner.name for runner in github_info if runner.online]
        logger.info("Found %s existing openstack runners", len(online_runners))

        with _create_connection(self._cloud_config) as conn:
            runner_by_health = self._get_openstack_runner_status(conn)

            # Clean up offline runners.
            if runner_by_health.unhealthy:
                self._remove_runners()
                raise NotImplementedError()

            delta = quantity - len(runner_by_health.healthy)

            # Spawn new runners
            if delta > 0:
                self._create_runner(conn)
            elif delta < 0:
                self._remove_runners()
            else:
                logger.info("No changes to number of runners needed")

            return delta
