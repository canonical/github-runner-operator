# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# 2024/04/11 The module contains too many lines which are scheduled for refactoring.
# pylint: disable=too-many-lines

"""Module for handling interactions with OpenStack."""
import json
import logging
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, Literal, NamedTuple, Optional, cast

import jinja2
import openstack
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
from fabric import Connection as SshConnection
from invoke.runners import Result
from openstack.compute.v2.server import Server
from openstack.connection import Connection as OpenstackConnection
from openstack.exceptions import OpenStackCloudException, SDKException
from paramiko.ssh_exception import NoValidConnectionsError

import metrics
from charm_state import (
    Arch,
    GithubOrg,
    ProxyConfig,
    SSHDebugConnection,
    UnsupportedArchitectureError,
)
from errors import (
    CreateMetricsStorageError,
    GithubClientError,
    IssueMetricEventError,
    OpenStackError,
    OpenstackImageBuildError,
    OpenstackInstanceLaunchError,
    RunnerBinaryError,
    RunnerCreateError,
    RunnerStartError,
    SubprocessError,
)
from github_client import GithubClient
from github_type import GitHubRunnerStatus, RunnerApplication, SelfHostedRunner
from openstack_cloud import metrics_storage
from runner_manager_type import OpenstackRunnerManagerConfig
from runner_metrics import RUNNER_INSTALLED_TS_FILE_NAME
from runner_type import GithubPath, RunnerByHealth, RunnerGithubInfo
from utilities import execute_command, retry, set_env_var

logger = logging.getLogger(__name__)

IMAGE_PATH_TMPL = "jammy-server-cloudimg-{architecture}-compressed.img"
# Update the version when the image is not backward compatible.
IMAGE_NAME = "github-runner-jammy-v1"
# Update the version when the security group rules are not backward compatible.
SECURITY_GROUP_NAME = "github-runner-v1"
BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"
_SSH_KEY_PATH = Path("/home/ubuntu/.ssh")
_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/github-runner")
METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"

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
        OpenStackError: if the credentials provided is not authorized.

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
        logger.exception("OpenStack API call failure")
        raise OpenStackError("Failed OpenStack API call") from exc


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

    Attributes:
        name: Name of the image to launch the GitHub runner instance with.
        labels: The runner instance labels.
        registration_token: Token for registering the runner on GitHub.
        github_path: The GitHub repo/org path to register the runner.
        openstack_image: The Openstack image to use to boot the instance with.
    """

    name: str
    labels: Iterable[str]
    registration_token: str
    github_path: GithubPath
    openstack_image: str


SupportedCloudImageArch = Literal["amd64", "arm64"]


def _get_supported_runner_arch(arch: str) -> SupportedCloudImageArch:
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


def _get_openstack_architecture(arch: Arch) -> str:
    """Get openstack architecture.

    See https://docs.openstack.org/glance/latest/admin/useful-image-properties.html

    Args:
        arch: The architecture the runner is running on.

    Raises:
        UnsupportedArchitectureError: If an unsupported architecture was passed.

    Returns:
        The architecture formatted for openstack image property.
    """
    match arch:
        case arch.X64:
            return "x86_64"
        case arch.ARM64:
            return "aarch64"
        case _:
            raise UnsupportedArchitectureError(arch)


class OpenstackUpdateImageError(Exception):
    """Represents an error while updating image on Openstack."""


@retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
def _update_image(
    cloud_config: dict[str, dict], ubuntu_image_arch: str, openstack_image_arch: str
) -> int:
    """Update the openstack image if it exists, create new otherwise.

    Args:
        cloud_config: The cloud configuration to connect OpenStack with.
        ubuntu_image_arch: The cloud-image architecture.
        openstack_image_arch: The Openstack image architecture.

    Raises:
        OpenstackUpdateImageError: If there was an error interacting with images on Openstack.

    Returns:
        The created image ID.
    """
    try:
        with _create_connection(cloud_config) as conn:
            existing_image: openstack.image.v2.image.Image
            for existing_image in conn.search_images(name_or_id=IMAGE_NAME):
                # images with same name (different ID) can be created and will error during server
                # instantiation.
                if not conn.delete_image(name_or_id=existing_image.id, wait=True):
                    raise OpenstackUpdateImageError(
                        "Failed to delete duplicate image on Openstack."
                    )
            image: openstack.image.v2.image.Image = conn.create_image(
                name=IMAGE_NAME,
                filename=IMAGE_PATH_TMPL.format(architecture=ubuntu_image_arch),
                wait=True,
                properties={"architecture": openstack_image_arch},
            )
            return image.id
    except OpenStackCloudException as exc:
        raise OpenstackUpdateImageError("Failed to upload image.") from exc


# Ignore the flake8 function too complex (C901). The function does not have much logic, the lint
# is likely triggered with the multiple try-excepts, which are needed.
def build_image(  # noqa: C901
    arch: Arch,
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubPath,
    proxies: Optional[ProxyConfig] = None,
) -> str:
    """Build and upload an image to OpenStack.

    Args:
        arch: The system architecture to build the image for.
        cloud_config: The cloud configuration to connect OpenStack with.
        github_client: The Github client to interact with Github API.
        path: Github organisation or repository path.
        proxies: HTTP proxy settings.

    Raises:
        OpenstackImageBuildError: If there were errors building/creating the image.

    Returns:
        The created OpenStack image id.
    """
    # Setting the env var to this process and any child process spawned.
    # Needed for GitHub API with GhApi used by GithubClient class.
    if proxies is not None:
        if no_proxy := proxies.no_proxy:
            set_env_var("NO_PROXY", no_proxy)
        if http_proxy := proxies.http:
            set_env_var("HTTP_PROXY", http_proxy)
        if https_proxy := proxies.https:
            set_env_var("HTTPS_PROXY", https_proxy)

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
        return _update_image(
            cloud_config=cloud_config,
            ubuntu_image_arch=image_arch,
            openstack_image_arch=_get_openstack_architecture(arch),
        )
    except OpenstackUpdateImageError as exc:
        raise OpenstackImageBuildError(f"Failed to update image, {exc}") from exc


# Disable too many arguments, as they are needed to create the dataclass.
def create_instance_config(  # pylint: disable=too-many-arguments
    app_name: str,
    unit_num: int,
    openstack_image: str,
    path: GithubPath,
    labels: Iterable[str],
    github_client: GithubClient,
) -> InstanceConfig:
    """Create an instance config from charm data.

    Args:
        app_name: The juju application name.
        unit_num: The juju unit number.
        openstack_image: The openstack image object to create the instance with.
        path: Github organisation or repository path.
        labels: Addition labels for the runner.
        github_client: The Github client to interact with Github API.

    Returns:
        Instance configuration created.
    """
    suffix = secrets.token_hex(12)
    registration_token = github_client.get_runner_registration_token(path=path)
    return InstanceConfig(
        name=f"{app_name}-{unit_num}-{suffix}",
        labels=("jammy", *labels),
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
        pre_job_script=str(PRE_JOB_SCRIPT),
        dockerhub_mirror=dockerhub_mirror or "",
        ssh_debug_info=(secrets.choice(ssh_debug_connections) if ssh_debug_connections else None),
    )


def _generate_cloud_init_userdata(
    templates_env: jinja2.Environment, instance_config: InstanceConfig, runner_env: str, pre_job_contents: str
) -> str:
    """Generate cloud init userdata to launch at startup.

    Args:
        templates_env: The jinja template environment.
        instance_config: The configuration values for Openstack instance to launch.
        runner_env: The contents of .env to source when launching Github runner.
        pre_job_contents: The contents of pre-job script to run before starting the job.

    Returns:
        The cloud init userdata script.
    """
    runner_group = None
    if isinstance(instance_config.github_path, GithubOrg):
        runner_group = instance_config.github_path.group

    return templates_env.get_template("openstack-userdata.sh.j2").render(
        github_url=f"https://github.com/{instance_config.github_path.path()}",
        runner_group=runner_group,
        token=instance_config.registration_token,
        instance_labels=",".join(instance_config.labels),
        instance_name=instance_config.name,
        env_contents=runner_env,
        pre_job_contents=pre_job_contents,
        metrics_exchange_path=str(METRICS_EXCHANGE_PATH)
    )


class GithubRunnerRemoveError(Exception):
    """Represents an error removing registered runner from Github."""


_INSTANCE_STATUS_SHUTOFF = "SHUTOFF"
_INSTANCE_STATUS_ACTIVE = "ACTIVE"


class OpenstackRunnerManager:
    """Runner manager for OpenStack-based instances.

    Attributes:
        app_name: The juju application name.
        unit_num: The juju unit number.
        instance_name: Prefix of the name for the set of runners.
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
            app_name: The juju application name.
            unit_num: The juju unit number.
            openstack_runner_manager_config: Configurations related to runner manager.
            cloud_config: The openstack clouds.yaml in dict format.
        """
        # Setting the env var to this process and any child process spawned.
        proxies = openstack_runner_manager_config.charm_state.proxy_config
        if no_proxy := proxies.no_proxy:
            set_env_var("NO_PROXY", no_proxy)
        if http_proxy := proxies.http:
            set_env_var("HTTP_PROXY", http_proxy)
        if https_proxy := proxies.https:
            set_env_var("HTTPS_PROXY", https_proxy)

        self.app_name = app_name
        self.unit_num = unit_num
        self.instance_name = f"{app_name}-{unit_num}"
        self._config = openstack_runner_manager_config
        self._cloud_config = cloud_config
        self._github = GithubClient(token=self._config.token)

    def _get_key_path(self, name: str) -> Path:
        """Get the filepath for storing private SSH of a runner.

        Args:
            name: The name of the runner.

        Returns:
            Path to reserved for the key file of the runner.
        """
        return _SSH_KEY_PATH / f"runner-{name}.key"

    # TODO: sonarlint gives python:S3776 : Cognitive Complexity of function is too high.
    def _ensure_security_group(self, conn: OpenstackConnection) -> None:
        """Ensure runner security group exists.

        Args:
            conn: The connection object to access OpenStack cloud.
        """
        rule_exists_icmp = False
        rule_exists_ssh = False
        rule_exists_tmate_ssh = False

        existing_security_group = conn.get_security_group(name_or_id=SECURITY_GROUP_NAME)
        if existing_security_group is None:
            logger.info("Security group %s not found, creating it", SECURITY_GROUP_NAME)
            conn.create_security_group(
                name=SECURITY_GROUP_NAME,
                description="For servers managed by the github-runner charm.",
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
                if (
                    rule["protocol"] == "tcp"
                    and rule["port_range_min"] == rule["port_range_max"] == 10022
                ):
                    logger.debug(
                        "Found tmate SSH rule in existing security group %s", SECURITY_GROUP_NAME
                    )
                    rule_exists_tmate_ssh = True

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
        if not rule_exists_tmate_ssh:
            conn.create_security_group_rule(
                secgroup_name_or_id=SECURITY_GROUP_NAME,
                port_range_min="10022",
                port_range_max="10022",
                protocol="tcp",
                direction="egress",
                ethertype="IPv4",
            )

    def _setup_runner_keypair(self, conn: OpenstackConnection, name: str) -> None:
        """Set up the SSH keypair for a runner.

        Args:
            conn: The connection object to access OpenStack cloud.
            name: The name of the runner.
        """
        private_key_path = self._get_key_path(name)

        if private_key_path.exists():
            logger.warning("Existing private key file for %s found, removing it.", name)
            private_key_path.unlink()

        keypair = conn.create_keypair(name=name)
        private_key_path.write_text(keypair.private_key)

    def _ssh_health_check(self, instance: Server) -> bool:
        """Use SSH to check whether runner application is running.

        Args:
            instance: The openstack compute instance to check connections.

        Returns:
            Whether the runner application is running.
        """
        for ssh_conn in self._get_ssh_connections(instance=instance):
            instance_name = instance.instance_name
            try:
                result = ssh_conn.run("ps aux")
                logger.debug("Output of `ps aux` on %s stderr: %s", instance_name, result.stderr)
                logger.debug("Output of `ps aux` on %s stdout: %s", instance_name, result.stdout)
                if not result.ok:
                    logger.warning("List all process command failed on %s ", instance_name)
                    continue

                if "/bin/bash /home/ubuntu/actions-runner/run.sh" in result.stdout:
                    logger.info("Runner process found to be healthy on %s", instance_name)
                    return True

            except NoValidConnectionsError:
                logger.info("Unable to SSH into %s with address %s", instance_name, ssh_conn.host)
                # Looping over all IP and trying SSH.

        logger.error(
            "Unable to SSH into %s with any address on network %s",
            instance.instance_name,
            self._config.network,
        )
        return False

    @retry(tries=10, delay=30, local_logger=logger)
    def _wait_until_runner_process_running(
        self, conn: OpenstackConnection, instance_name: str
    ) -> None:
        """Wait until the runner process is running.

        The waiting to done by the retry declarator.

        Args:
            conn: The openstack connection instance.
            instance_name: The name of the instance to wait on.

        Raises:
            RunnerStartError: Unable perform health check of the runner application.
        """
        try:
            server: Server | None = conn.get_server(instance_name)
            if (
                not server
                or server.status != _INSTANCE_STATUS_ACTIVE
                or not self._ssh_health_check(instance=server)
            ):
                raise RunnerStartError(
                    (
                        "Unable to find running process of runner application on openstack runner "
                        f"{instance_name}"
                    )
                )
        except TimeoutError as err:
            raise RunnerStartError(
                f"Unable to connect to openstack runner {instance_name}"
            ) from err

    def _create_runner(self, conn: OpenstackConnection) -> None:
        """Create a runner on OpenStack cloud.

        Args:
            conn: The connection object to access OpenStack cloud.

        Raises:
            RunnerCreateError: Unable to create the OpenStack runner.
        """
        ts_now = time.time()
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True
        )

        env_contents = _generate_runner_env(
            templates_env=environment,
            proxies=self._config.charm_state.proxy_config,
            dockerhub_mirror=self._config.dockerhub_mirror,
            ssh_debug_connections=self._config.charm_state.ssh_debug_connections,
        )
        pre_job_contents = environment.get_template("pre-job.j2").render(
            issue_metrics=True,
            do_repo_policy_check=True,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH)
        )
        instance_config = create_instance_config(
            self.app_name,
            self.unit_num,
            IMAGE_NAME,
            self._config.path,
            self._config.labels,
            self._github,
        )
        cloud_userdata = _generate_cloud_init_userdata(
            templates_env=environment, instance_config=instance_config, runner_env=env_contents, pre_job_contents=pre_job_contents,
        )

        self._ensure_security_group(conn)
        self._setup_runner_keypair(conn, instance_config.name)

        logger.info("Creating runner %s", instance_config.name)
        try:
            instance = conn.create_server(
                name=instance_config.name,
                image=IMAGE_NAME,
                key_name=instance_config.name,
                flavor=self._config.flavor,
                network=self._config.network,
                security_groups=[SECURITY_GROUP_NAME],
                userdata=cloud_userdata,
                auto_ip=False,
                timeout=120,
                wait=True,
            )
        except openstack.exceptions.ResourceTimeout as err:
            logger.exception("Timeout creating OpenStack runner %s", instance_config.name)
            try:
                logger.info(
                    "Attempting to remove OpenStack runner %s that timeout on creation",
                    instance_config.name,
                )
                conn.delete_server(name_or_id=instance_config.name, wait=True)
            except openstack.exceptions.SDKException:
                logger.critical(
                    "Cleanup of creation failure runner %s has failed", instance_config.name
                )
                # Reconcile will attempt to cleanup again prior to spawning new runners.
            raise RunnerCreateError(
                f"Timeout creating OpenStack runner {instance_config.name}"
            ) from err

        logger.info("Waiting runner %s to come online", instance_config.name)
        self._wait_until_runner_process_running(conn, instance.name)
        logger.info("Finished creating runner %s", instance_config.name)
        ts_after = time.time()
        try:
            metrics.issue_event(
                event=metrics.RunnerInstalled(
                    timestamp=ts_after,
                    flavor=self.app_name,
                    duration=ts_after - ts_now,
                ),
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue RunnerInstalled metric")

        try:
            storage = metrics_storage.create(instance_config.name)
        except CreateMetricsStorageError:
            logger.exception(
                "Failed to get shared filesystem for runner %s, "
                "will not be able to issue all metrics.",
                instance_config.name,
            )
        else:
            try:
                (storage.path / RUNNER_INSTALLED_TS_FILE_NAME).write_text(
                    str(ts_after), encoding="utf-8"
                )
            except FileNotFoundError:
                logger.exception(
                    "Failed to write runner-installed.timestamp into shared filesystem "
                    "for runner %s, will not be able to issue all metrics.",
                    instance_config.name,
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
                runner.name,
                runner.id,
                runner.status == GitHubRunnerStatus.ONLINE,
                runner.busy,
            )
            for runner in remote_runners_list
            if runner.name.startswith(f"{self.instance_name}-")
        )

    def _get_ssh_connections(self, instance: Server) -> Generator[SshConnection, None, None]:
        """Get ssh connections within a network for a given openstack instance.

        Args:
            instance: The Openstack server instance.

        Yields:
            Openstack SSH connections.
        """
        if not cast(dict, instance.addresses).get(self._config.network, None):
            logger.error(
                "Instance %s created under invalid or no network %s",
                instance.instance_name,
                instance.addresses,
            )
            return
        for address in instance.addresses[self._config.network]:
            ip = address["addr"]
            yield SshConnection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(self._get_key_path(instance.name))},
                connect_timeout=10,
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
            for instance in cast(list[Server], conn.list_servers())
            if instance.name.startswith(f"{self.instance_name}-")
        ]

        logger.debug("Found openstack instances: %s", openstack_instances)

        for instance in openstack_instances:
            server: Server | None = conn.get_server(instance.name)
            if not server:
                continue
            # SHUTOFF runners are runners that have completed executing jobs.
            if server.status == _INSTANCE_STATUS_SHUTOFF or not self._ssh_health_check(
                instance=server
            ):
                unhealthy_runner.append(instance.name)
            else:
                healthy_runner.append(instance.name)

        return RunnerByHealth(healthy=tuple(healthy_runner), unhealthy=tuple(unhealthy_runner))

    def _run_github_removal_script(self, instance: Server, remove_token: str | None) -> None:
        """Run Github runner removal script.

        Args:
            instance: The Openstack server instance.
            remove_token: The GitHub instance removal token.

        Raises:
            GithubRunnerRemoveError: Unable to remove runner from GitHub.
        """
        if not remove_token:
            return
        for ssh_conn in self._get_ssh_connections(instance=instance):
            try:
                result: Result = ssh_conn.run(
                    f"{_CONFIG_SCRIPT_PATH} remove --token {remove_token}"
                )
                if not result.ok:
                    logger.warning(
                        (
                            "Unable to run removal script on instance %s, "
                            "exit code: %s, stdout: %s, stderr: %s"
                        ),
                        instance.instance_name,
                        result.return_code,
                        result.stdout,
                        result.stderr,
                    )
                    continue
                return
            except NoValidConnectionsError:
                logger.info(
                    "Unable to SSH into %s with address %s", instance.instance_name, ssh_conn.host
                )
                continue

        logger.warning("Failed to run GitHub runner removal script %s", instance.instance_name)
        raise GithubRunnerRemoveError(f"Failed to remove runner {instance.name} from Github.")

    def _remove_one_runner(
        self,
        conn: OpenstackConnection,
        instance_name: str,
        github_id: int | None = None,
        remove_token: str | None = None,
    ) -> None:
        """Remove one OpenStack runner.

        Args:
            conn: The Openstack connection instance.
            instance_name: The Openstack server name to delete.
            github_id: The runner id on GitHub.
            remove_token: The GitHub runner remove token.
        """
        logger.info("Attempting to remove OpenStack runner %s", instance_name)

        server: Server | None = conn.get_server(name_or_id=instance_name)
        if server is None:
            return

        if server.status == _INSTANCE_STATUS_ACTIVE:
            self._pull_metrics(server, instance_name)
            self._run_github_removal_script(instance=server, remove_token=remove_token)
        elif github_id is not None:
            try:
                self._github.delete_runner(self._config.path, github_id)
            except GithubClientError as exc:
                logger.warning("Failed to remove runner from Github %s, %s", instance_name, exc)

        try:
            if not conn.delete_server(name_or_id=instance_name, wait=True, delete_ips=True):
                logger.warning("Server does not exist %s", instance_name)
        except SDKException as exc:
            logger.error("Something wrong deleting the server %s, %s", instance_name, str(exc))

    def _pull_metrics(self, instance: Server, instance_name: str) -> None:
        try:
            storage = metrics_storage.get(instance_name)
        except CreateMetricsStorageError:
            logger.exception(
                "Failed to get shared metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                instance_name,
            )
            return

        for ssh_conn in self._get_ssh_connections(instance=instance):
            if not self._pull_file(ssh_conn, instance, str(METRICS_EXCHANGE_PATH / "pre-job-metrics.json"), str(storage.path / "pre-job-metrics.json")):
                continue
            if not self._pull_file(ssh_conn, instance, str(METRICS_EXCHANGE_PATH / "post-job-metrics.json"), str(storage.path / "post-job-metrics.json")):
                continue
            return

        logger.error("Failed to fetch runner metrics for  %s . Will not be able to issue metrics.", instance.instance_name)

    def _pull_file(self, ssh_conn: SshConnection, instance: Server, file_path: str, local_path: str) -> bool:
        try:
            ssh_conn.get(remote=file_path, local=local_path)
        except NoValidConnectionsError:
            logger.info(
                "Unable to SSH into %s with address %s", instance.instance_name, ssh_conn.host
            )
            return False
        except OSError as exc:
            logger.info("Error retrieving file %s on %s: %s", file_path, instance.instance_name, str(exc))
            return False

        return True

    def _remove_runners(
        self,
        conn: OpenstackConnection,
        instance_names: Iterable[str],
        remove_token: str | None = None,
        num_to_remove: int | float | None = None,
    ) -> None:
        """Delete runners on Openstack.

        Removes the registered runner from Github if remove_token is provided.

        Args:
            conn: The Openstack connection instance.
            instance_names: The Openstack server names to delete.
            remove_token: The GitHub runner remove token.
            num_to_remove: Remove a specified number of runners. Remove all if None.
        """
        if num_to_remove is None:
            num_to_remove = float("inf")

        name_to_github_id = {
            runner["name"]: runner["id"]
            for runner in self._github.get_runner_github_info(self._config.path)
        }
        for instance_name in instance_names:
            if num_to_remove < 1:
                break

            github_id = name_to_github_id.get(instance_name, None)
            self._remove_one_runner(conn, instance_name, github_id, remove_token)

            # Attempt to delete the keys. This is place at the end of deletion, so we can access
            # the instances that failed to delete on previous tries.
            try:
                conn.delete_keypair(instance_name)
            except openstack.exceptions.SDKException:
                logger.exception("Unable to delete OpenStack keypair %s", instance_name)
            self._get_key_path(instance_name).unlink(missing_ok=True)
            num_to_remove -= 1

    def _clean_up_keys(self, conn: OpenstackConnection, exclude_instances: Iterable[str]) -> None:
        """Delete all SSH keys except the specified instances.

        Args:
            conn: The Openstack connection instance.
            exclude_instances: The keys of these instance will not be deleted.
        """
        logger.info("Cleaning up SSH keys")
        exclude_filename = set(self._get_key_path(instance) for instance in exclude_instances)

        for path in _SSH_KEY_PATH.iterdir():
            # Find key file from this application.
            if (
                path.is_file()
                and path.name.startswith(self.instance_name)
                and path.name.endswith(".key")
            ):
                if path.name in exclude_filename:
                    continue

                keypair_name = path.name.split(".")[0]
                try:
                    conn.delete_keypair(keypair_name)
                except openstack.exceptions.SDKException:
                    logger.warning(
                        "Unable to delete OpenStack keypair associated with deleted key file %s ",
                        path.name,
                    )

                path.unlink()

    def reconcile(self, quantity: int) -> int:
        """Reconcile the quantity of runners.

        Args:
            quantity: The number of intended runners.

        Raises:
            OpenstackInstanceLaunchError: Unable to launch OpenStack instance.

        Returns:
            The change in number of runners.
        """
        github_info = self.get_github_runner_info()
        online_runners = [runner for runner in github_info if runner.online]
        offline_runners = [runner for runner in github_info if not runner.online]
        logger.info("Found %s existing openstack runners", len(online_runners))
        logger.info("Found %s existing offline openstack runners", len(offline_runners))

        with _create_connection(self._cloud_config) as conn:
            runner_by_health = self._get_openstack_runner_status(conn)
            logger.info(
                "Found %s healthy runner and %s unhealthy runner",
                len(runner_by_health.healthy),
                len(runner_by_health.unhealthy),
            )
            logger.debug("Healthy runner: %s", runner_by_health.healthy)
            logger.debug("Unhealthy runner: %s", runner_by_health.unhealthy)

            # Clean up offline (SHUTOFF) runners or unhealthy (no connection/cloud-init script)
            # runners.
            remove_token = self._github.get_runner_remove_token(path=self._config.path)
            instance_to_remove = (
                *runner_by_health.unhealthy,
                *(runner.runner_name for runner in offline_runners),
            )
            self._remove_runners(
                conn=conn, instance_names=instance_to_remove, remove_token=remove_token
            )
            # Clean up orphan keys, e.g., If openstack instance is removed externally the key
            # would not be deleted.
            self._clean_up_keys(conn, runner_by_health.healthy)

            delta = quantity - len(runner_by_health.healthy)

            # Spawn new runners
            if delta > 0:
                # Skip this reconcile if image not present.
                try:
                    if conn.get_image(name_or_id=IMAGE_NAME) is None:
                        logger.warning(
                            "No OpenStack runner was spawned due to image needed not found"
                        )
                        return 0
                except openstack.exceptions.SDKException as exc:
                    # Will be resolved by charm integration with image build charm.
                    logger.exception("Multiple image named %s found", IMAGE_NAME)
                    raise OpenstackInstanceLaunchError(
                        "Multiple image found, unable to determine the image to use"
                    ) from exc

                logger.info("Creating %s OpenStack runners", delta)
                self._create_runner(conn)
            elif delta < 0:
                logger.info("Removing %s OpenStack runners", delta)
                self._remove_runners(
                    conn=conn,
                    instance_names=runner_by_health.healthy,
                    remove_token=remove_token,
                    num_to_remove=abs(delta),
                )
            else:
                logger.info("No changes to number of runners needed")
            return delta

    def flush(self) -> int:
        """Flush Openstack servers.

        Returns:
            The number of runners flushed.
        """
        logger.info("Flushing OpenStack all runners")
        with _create_connection(self._cloud_config) as conn:
            runner_by_health = self._get_openstack_runner_status(conn)
            remove_token = self._github.get_runner_remove_token(path=self._config.path)
            runners_to_delete = (*runner_by_health.healthy, *runner_by_health.unhealthy)
            self._remove_runners(
                conn=conn,
                instance_names=runners_to_delete,
                remove_token=remove_token,
            )
            return len(runners_to_delete)
