# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manage the lifecycle of runners.

The `Runner` class stores the information on the runners and manages the
lifecycle of the runners on LXD and GitHub.

The `RunnerManager` class from `runner_manager.py` creates and manages a
collection of `Runner` instances.
"""

import json
import logging
import pathlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import yaml

import errors
import shared_fs
from errors import (
    LxdError,
    RunnerCreateError,
    RunnerError,
    RunnerFileLoadError,
    RunnerRemoveError,
    SubprocessError,
)
from lxd import LxdInstance
from lxd_type import LxdInstanceConfig
from runner_type import (
    GitHubOrg,
    GitHubRepo,
    RunnerClients,
    RunnerConfig,
    RunnerStatus,
    VirtualMachineResources,
)
from utilities import execute_command, retry

logger = logging.getLogger(__name__)
LXD_PROFILE_YAML = pathlib.Path(__file__).parent.parent / "lxd-profile.yaml"
if not LXD_PROFILE_YAML.exists():
    LXD_PROFILE_YAML = LXD_PROFILE_YAML.parent / "lxd-profile.yml"


@dataclass
class WgetExecutable:
    """The executable to be installed through wget.

    Args:
        url: The URL of the executable binary.
        cmd: Executable command name. E.g. yq_linux_amd64 -> yq
    """

    url: str
    cmd: str


class Runner:
    """Single instance of GitHub self-hosted runner.

    Attrs:
        app_name (str): Name of the charm.
        path (GitHubPath): Path to GitHub repo or org.
        proxies (ProxySetting): HTTP proxy setting for juju charm.
        name (str): Name of the runner instance.
        exist (bool): Whether the runner instance exists on LXD.
        online (bool): Whether GitHub marks this runner as online.
        busy (bool): Whether GitHub marks this runner as busy.
    """

    runner_application = Path("/home/ubuntu/github-runner")
    env_file = runner_application / ".env"
    config_script = runner_application / "config.sh"
    runner_script = runner_application / "start.sh"
    pre_job_script = runner_application / "pre-job.sh"

    def __init__(
        self,
        clients: RunnerClients,
        runner_config: RunnerConfig,
        runner_status: RunnerStatus,
        instance: Optional[LxdInstance] = None,
    ):
        """Construct the runner instance.

        Args:
            clients: Clients to access various services.
            runner_config: Configuration of the runner instance.
            instance: LXD instance of the runner if already created.
        """
        # Dependency injection to share the instances across different `Runner` instance.
        self._clients = clients
        self.config = runner_config
        self.status = runner_status
        self.instance = instance

        self._shared_fs: Optional[shared_fs.SharedFilesystem] = None

        # If the proxy setting are set, then add NO_PROXY local variables.
        if self.config.proxies.get("http") or self.config.proxies.get("https"):
            if self.config.proxies.get("no_proxy"):
                self.config.proxies["no_proxy"] += ","
            self.config.proxies["no_proxy"] += f"{self.config.name},.svc"

    def create(
        self,
        image: str,
        resources: VirtualMachineResources,
        binary_path: Path,
        registration_token: str,
    ):
        """Create the runner instance on LXD and register it on GitHub.

        Args:
            image: Name of the image to launch the LXD instance with.
            resources: Resource setting for the LXD instance.
            binary_path: Path to the runner binary.
            registration_token: Token for registering the runner on GitHub.

        Raises:
            RunnerCreateError: Unable to create an LXD instance for runner.
        """
        logger.info("Creating runner: %s", self.config.name)

        try:
            if self.config.issue_metrics:
                try:
                    self._shared_fs = shared_fs.create(self.config.name)
                except errors.CreateSharedFilesystemError:
                    logger.exception(
                        "Unable to create shared filesystem for runner %s. "
                        "Will not create metrics for this runner.",
                        self.config.name,
                    )

            self.instance = self._create_instance(image, resources)
            self._start_instance()
            # Wait some initial time for the instance to boot up
            time.sleep(60)
            self._wait_boot_up()
            self._install_binary(binary_path)
            self._configure_runner()

            self._register_runner(registration_token, labels=[self.config.app_name, image])
            self._start_runner()
        except (RunnerError, LxdError) as err:
            raise RunnerCreateError(f"Unable to create runner {self.config.name}") from err

    def remove(self, remove_token: str) -> None:
        """Remove this runner instance from LXD and GitHub.

        Args:
            remove_token: Token for removing the runner on GitHub.

        Raises:
            RunnerRemoveError: Failure in removing runner.
        """
        logger.info("Removing runner: %s", self.config.name)

        if self.instance:
            logger.info("Executing command to removal of runner and clean up...")
            self.instance.execute(
                [
                    "/usr/bin/sudo",
                    "-u",
                    "ubuntu",
                    str(self.config_script),
                    "remove",
                    "--token",
                    remove_token,
                ],
                hide_cmd=True,
            )

            if self.instance.status == "Running":
                logger.info("Removing LXD instance of runner: %s", self.config.name)
                try:
                    self.instance.stop(wait=True, timeout=60)
                except LxdError:
                    logger.exception(
                        "Unable to gracefully stop runner %s within timeout.", self.config.name
                    )
                    logger.info("Force stopping of runner %s", self.config.name)
                    try:
                        self.instance.stop(force=True)
                    except LxdError as err:
                        raise RunnerRemoveError(f"Unable to remove {self.config.name}") from err
            else:
                # Delete ephemeral instances that have error or stopped status which LXD failed to
                # clean up.
                logger.warning(
                    "Found runner %s with status %s, forcing deletion",
                    self.config.name,
                    self.instance.status,
                )
                try:
                    self.instance.delete(wait=True)
                except LxdError as err:
                    raise RunnerRemoveError(f"Unable to remove {self.config.name}") from err

        if self.status.runner_id is None:
            return

        logger.info("Removing runner on GitHub: %s", self.config.name)

        # The runner should cleanup itself.  Cleanup on GitHub in case of runner cleanup error.
        if isinstance(self.config.path, GitHubRepo):
            logger.debug(
                "Ensure runner %s with id %s is removed from GitHub repo %s/%s",
                self.config.name,
                self.status.runner_id,
                self.config.path.owner,
                self.config.path.repo,
            )
            self._clients.github.actions.delete_self_hosted_runner_from_repo(
                owner=self.config.path.owner,
                repo=self.config.path.repo,
                runner_id=self.status.runner_id,
            )
        if isinstance(self.config.path, GitHubOrg):
            logger.debug(
                "Ensure runner %s with id %s is removed from GitHub org %s",
                self.config.name,
                self.status.runner_id,
                self.config.path.org,
            )
            self._clients.github.actions.delete_self_hosted_runner_from_org(
                org=self.config.path.org,
                runner_id=self.status.runner_id,
            )

    def _add_shared_filesystem(self):
        """Add the shared filesystem to the runner instance."""
        try:
            execute_command(
                [
                    "sudo",
                    "lxc",
                    "config",
                    "device",
                    "add",
                    self.config.name,
                    "metrics",
                    "disk",
                    f"source={self._shared_fs.path}",
                    "path=/metrics-exchange",
                ],
                check_exit=True,
            )
        except SubprocessError:
            logger.exception(
                "Unable to add shared filesystem to runner %s. "
                "Will not create metrics for this runner.",
                self.config.name,
            )

    @retry(tries=5, delay=1, local_logger=logger)
    def _create_instance(
        self, image: str, resources: VirtualMachineResources, ephemeral: bool = True
    ) -> LxdInstance:
        """Create an instance of runner.

        Args:
            image: Image used to launch the instance hosting the runner.
            resources: Configuration of the virtual machine resources.
            ephemeral: Whether the instance is ephemeral.

        Returns:
            LXD instance of the runner.
        """
        logger.info("Creating an LXD instance for runner: %s", self.config.name)

        self._ensure_runner_storage_pool()
        self._ensure_runner_profile()
        resource_profile = self._get_resource_profile(resources)

        # Create runner instance.
        instance_config: LxdInstanceConfig = {
            "name": self.config.name,
            "type": "container" if LXD_PROFILE_YAML.exists() else "virtual-machine",
            "source": {
                "type": "image",
                "mode": "pull",
                "server": "https://cloud-images.ubuntu.com/daily",
                "protocol": "simplestreams",
                "alias": image,
            },
            "ephemeral": ephemeral,
            "profiles": ["default", "runner", resource_profile],
        }

        try:
            instance = self._clients.lxd.instances.create(config=instance_config, wait=True)
        except LxdError:
            logger.exception(
                "Removing resource profile and storage profile due to LXD instance create failure"
            )

            # LxdError on creating LXD instance could be caused by improper initialization of
            # storage pool. If other runner LXD instance exists then it cannot be the cause.
            if not self._clients.lxd.instances.all():
                # Removing the storage pool and retry can solve the problem.
                self._remove_runner_storage_pool()
            raise

        self.status.exist = True

        if self._shared_fs:
            self._add_shared_filesystem()

        return instance

    @retry(tries=5, delay=1, local_logger=logger)
    def _ensure_runner_profile(self) -> None:
        """Ensure the runner profile is present on LXD.

        Raises:
            RunnerError: Unable to create the runner profile.
        """
        if self._clients.lxd.profiles.exists("runner"):
            logger.info("Found existing runner LXD profile")
            return

        logger.info("Creating runner LXD profile")
        profile_config = {}
        profile_devices = {}
        if LXD_PROFILE_YAML.exists():
            additional_lxc_profile = yaml.safe_load(LXD_PROFILE_YAML.read_text())
            profile_config = {
                k: json.dumps(v) if isinstance(v, bool) else v
                for k, v in additional_lxc_profile["config"].items()
            }
            profile_devices = additional_lxc_profile["devices"]
        self._clients.lxd.profiles.create("runner", profile_config, profile_devices)

        # Verify the action is successful.
        if not self._clients.lxd.profiles.exists("runner"):
            raise RunnerError("Failed to create runner LXD profile")

    @retry(tries=5, delay=5, local_logger=logger)
    def _ensure_runner_storage_pool(self) -> None:
        """Ensure the runner storage pool exists."""
        if self._clients.lxd.storage_pools.exists("runner"):
            logger.info("Found existing runner LXD storage pool.")
            return

        logger.info("Creating runner LXD storage pool.")
        self._clients.lxd.storage_pools.create(
            {
                "name": "runner",
                "driver": "dir",
                "config": {"source": str(self.config.lxd_storage_path)},
            }
        )

        # Verify the action is successful.
        if not self._clients.lxd.storage_pools.exists("runner"):
            raise RunnerError("Failed to create runner LXD storage pool")

    def _remove_runner_storage_pool(self) -> None:
        """Remove the runner storage pool if exists."""
        if self._clients.lxd.storage_pools.exists("runner"):
            logger.info("Removing existing runner LXD storage pool.")
            runner_storage_pool = self._clients.lxd.storage_pools.get("runner")

            # The resource profile needs to be removed first as it uses the storage pool.
            for used_by in runner_storage_pool.used_by:
                _, profile_name = used_by.rsplit("/", 1)
                profile = self._clients.lxd.profiles.get(profile_name)
                profile.delete()

            runner_storage_pool.delete()

    @classmethod
    def _get_resource_profile_name(cls, cpu: int, memory: str, disk: str) -> str:
        """Get the LXD profile name for resource limit.

        Args:
            cpu: CPU resource limit.
            memory: Memory resource limit.
            disk: Disk resource limit.

        Returns:
            Name for the LXD profile of the given resource limits.
        """
        return f"cpu-{cpu}-mem-{memory}-disk-{disk}"

    @retry(tries=5, delay=1, local_logger=logger)
    def _get_resource_profile(self, resources: VirtualMachineResources) -> str:
        """Get the LXD profile name of given resource limit.

        Args:
            resources: Resources limit of the runner instance.

        Raises:
            RunnerError: Unable to create the profile on LXD.

        Returns:
            str: Name of the profile for the given resource limit.
        """
        # Ensure the resource profile exists.
        profile_name = self._get_resource_profile_name(
            resources.cpu, resources.memory, resources.disk
        )
        if not self._clients.lxd.profiles.exists(profile_name):
            logger.info("Creating LXD profile for resource usage.")
            try:
                resource_profile_config = {
                    "limits.cpu": str(resources.cpu),
                    "limits.memory": resources.memory,
                }
                resource_profile_devices = {
                    "root": {
                        "path": "/",
                        "pool": "runner",
                        "type": "disk",
                        "size": resources.disk,
                    }
                }
                # Temporary fix to allow tmpfs to work for LXD VM.
                if not LXD_PROFILE_YAML.exists():
                    resource_profile_devices["root"]["io.cache"] = "unsafe"

                self._clients.lxd.profiles.create(
                    profile_name, resource_profile_config, resource_profile_devices
                )
            except LxdError as error:
                logger.error(error)
                raise RunnerError(
                    "Resources were not provided in the correct format, check the juju config for "
                    "cpu, memory and disk."
                ) from error

            # Verify the action is successful.
            if not self._clients.lxd.profiles.exists(profile_name):
                raise RunnerError(f"Unable to create {profile_name} LXD profile")
        else:
            logger.info("Found existing LXD profile for resource usage.")

        return profile_name

    @retry(tries=5, delay=1, local_logger=logger)
    def _start_instance(self) -> None:
        """Start an instance and wait for it to boot.

        Args:
            reconcile_interval: Time in seconds of period between each reconciliation.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        logger.info("Starting LXD instance for runner: %s", self.config.name)

        # Setting `wait=True` only ensure the instance has begin to boot up.
        self.instance.start(wait=True)

    @retry(tries=20, delay=30, local_logger=logger)
    def _wait_boot_up(self) -> None:
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        # Wait for the instance to finish to boot up and network to be up.
        if self.instance.execute(["/usr/bin/who"])[0] != 0:
            raise RunnerError("Runner system is not ready")
        if self.instance.execute(["/usr/bin/nslookup", "github.com"])[0] != 0:
            raise RunnerError("Runner network is not ready")

        logger.info("Finished booting up LXD instance for runner: %s", self.config.name)

    @retry(tries=5, delay=1, local_logger=logger)
    def _install_binary(self, binary: Path) -> None:
        """Load GitHub self-hosted runner binary on to the runner instance.

        Args:
            binary: Path to the compressed runner binary.

        Raises:
            RunnerFileLoadError: Unable to load the file into the runner instance.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        # TEMP: Install common tools used in GitHub Actions. This will be removed once virtual
        # machines are created from custom images/GitHub runner image.

        # Pre-create the microk8s group and add the user to it.
        self.instance.execute(["/usr/sbin/groupadd", "microk8s"])
        self.instance.execute(["/usr/sbin/usermod", "-aG", "microk8s", "ubuntu"])

        self._apt_install(["docker.io", "npm", "python3-pip", "shellcheck", "jq", "wget"])
        self._wget_install(
            [
                WgetExecutable(
                    url="https://github.com/mikefarah/yq/releases/download/v4.34.1/yq_linux_amd64",
                    cmd="yq",
                )
            ]
        )

        # Add the user to docker group.
        self.instance.execute(["/usr/sbin/usermod", "-aG", "docker", "ubuntu"])
        # Allow traffic for docker user.
        self.instance.execute(["/usr/sbin/iptables", "-I", "DOCKER-USER", "-j", "ACCEPT"])

        # The LXD instance is meant to run untrusted workload. Hardcoding the tmp directory should
        # be fine.
        binary_path = "/tmp/runner.tgz"  # nosec B108

        logger.info("Installing runner binary on LXD instance: %s", self.config.name)

        # Creating directory and putting the file are idempotent, and can be retried.
        self.instance.files.mk_dir(str(self.runner_application))
        self.instance.files.push_file(str(binary), binary_path)

        self.instance.execute(
            ["/usr/bin/tar", "-xzf", binary_path, "-C", str(self.runner_application)]
        )
        self.instance.execute(
            ["/usr/bin/chown", "-R", "ubuntu:ubuntu", str(self.runner_application)]
        )

        # Verify the config script is written to runner.
        exit_code, _, stderr = self.instance.execute(["test", "-f", str(self.config_script)])
        if exit_code == 0:
            logger.info("Runner binary loaded on runner instance %s.", self.config.name)
        else:
            logger.error(
                "Unable to load runner binary on runner instance %s: %s",
                self.config.name,
                stderr.read(),
            )
            raise RunnerFileLoadError(f"Failed to load runner binary on {self.config.name}")

    def _should_render_templates_with_metrics(self) -> bool:
        """Whether to render templates with metrics.

        Returns:
            True if the runner should render templates with metrics.
        """
        return self._shared_fs is not None

    @retry(tries=5, delay=10, max_delay=60, backoff=2, local_logger=logger)
    def _configure_runner(self) -> None:
        """Load configuration on to the runner.

        Raises:
            RunnerFileLoadError: Unable to load configuration file on the runner.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        # Load the runner startup script.
        startup_contents = self._clients.jinja.get_template("start.j2").render(
            issue_metrics=self._should_render_templates_with_metrics()
        )
        self._put_file(str(self.runner_script), startup_contents, mode="0755")
        self.instance.execute(["/usr/bin/sudo", "chown", "ubuntu:ubuntu", str(self.runner_script)])
        self.instance.execute(["/usr/bin/sudo", "chmod", "u+x", str(self.runner_script)])

        # Load the runner pre-job script.
        bridge_address_range = self._clients.lxd.networks.get("lxdbr0").config["ipv4.address"]
        host_ip, _ = bridge_address_range.split("/")
        one_time_token = self._clients.repo.get_one_time_token()
        pre_job_contents = self._clients.jinja.get_template("pre-job.j2").render(
            host_ip=host_ip,
            one_time_token=one_time_token,
            issue_metrics=self._should_render_templates_with_metrics(),
        )
        self._put_file(str(self.pre_job_script), pre_job_contents)
        self.instance.execute(
            ["/usr/bin/sudo", "chown", "ubuntu:ubuntu", str(self.pre_job_script)]
        )
        self.instance.execute(["/usr/bin/sudo", "chmod", "u+x", str(self.pre_job_script)])

        # Set permission to the same as GitHub-hosted runner for this directory.
        # Some GitHub Actions require this permission setting to run.
        # As the user already has sudo access, this does not give the user any additional access.
        self.instance.execute(["/usr/bin/sudo", "chmod", "777", "/usr/local/bin"])

        # Load `/etc/environment` file.
        environment_contents = self._clients.jinja.get_template("environment.j2").render(
            proxies=self.config.proxies
        )
        self._put_file("/etc/environment", environment_contents)

        # Load `.env` config file for GitHub self-hosted runner.
        env_contents = self._clients.jinja.get_template("env.j2").render(
            proxies=self.config.proxies, pre_job_script=str(self.pre_job_script)
        )
        self._put_file(str(self.env_file), env_contents)
        self.instance.execute(["/usr/bin/chown", "ubuntu:ubuntu", str(self.env_file)])

        if self.config.proxies:
            # Creating directory and putting the file are idempotent, and can be retried.
            logger.info("Adding proxy setting to the runner.")

            docker_proxy_contents = self._clients.jinja.get_template(
                "systemd-docker-proxy.j2"
            ).render(proxies=self.config.proxies)

            # Set docker daemon proxy config
            docker_service_path = Path("/etc/systemd/system/docker.service.d")
            docker_service_proxy = docker_service_path / "http-proxy.conf"

            self.instance.files.mk_dir(str(docker_service_path))
            self._put_file(str(docker_service_proxy), docker_proxy_contents)

            self.instance.execute(["systemctl", "daemon-reload"])
            self.instance.execute(["systemctl", "restart", "docker"])

            # Set docker client proxy config
            docker_client_proxy = {
                "proxies": {
                    "default": {
                        "httpProxy": self.config.proxies["http"],
                        "httpsProxy": self.config.proxies["https"],
                        "noProxy": self.config.proxies["no_proxy"],
                    }
                }
            }
            docker_client_proxy_content = json.dumps(docker_client_proxy)
            # Configure the docker client for root user and ubuntu user.
            self._put_file("/root/.docker/config.json", docker_client_proxy_content)
            self._put_file("/home/ubuntu/.docker/config.json", docker_client_proxy_content)
            self.instance.execute(
                ["/usr/bin/chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/.docker"]
            )

        # Ensure the no existing /usr/bin/python.
        self.instance.execute(["rm", "/usr/bin/python"])
        # Make python an alias of python3.
        self.instance.execute(["ln", "-s", "/usr/bin/python3", "/usr/bin/python"])

    @retry(tries=5, delay=30, local_logger=logger)
    def _register_runner(self, registration_token: str, labels: Sequence[str]) -> None:
        """Register the runner on GitHub.

        Args:
            registration_token: Registration token request from GitHub.
            labels: Labels to tag the runner with.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        logger.info("Registering runner %s", self.config.name)

        register_cmd = [
            "/usr/bin/sudo",
            "-u",
            "ubuntu",
            str(self.config_script),
            "--url",
            f"https://github.com/{self.config.path.path()}",
            "--token",
            registration_token,
            "--ephemeral",
            "--unattended",
            "--labels",
            ",".join(labels),
            "--name",
            self.instance.name,
        ]

        if isinstance(self.config.path, GitHubOrg):
            register_cmd += ["--runnergroup", self.config.path.group]

        logger.info("Executing registration command...")
        self.instance.execute(
            register_cmd,
            cwd=str(self.runner_application),
            hide_cmd=True,
        )

    @retry(tries=5, delay=30, local_logger=logger)
    def _start_runner(self) -> None:
        """Start the GitHub runner."""
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        logger.info("Starting runner %s", self.config.name)

        self.instance.execute(
            [
                "/usr/bin/sudo",
                "-u",
                "ubuntu",
                str(self.runner_script),
            ]
        )

        logger.info("Started runner %s", self.config.name)

    def _put_file(self, filepath: str, content: str, mode: Optional[str] = None) -> None:
        """Put a file into the runner instance.

        Args:
            filepath: Path to load the file in the runner instance.
            content: Content of the file.

        Raises:
            RunnerFileLoadError: Failed to load the file into the runner instance.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        self.instance.files.write_file(filepath, content, mode)
        content_on_runner = self.instance.files.read_file(filepath)
        if content_on_runner != content:
            logger.error(
                "Loaded file %s in runner %s did not match expected content",
                filepath,
                self.instance.name,
            )
            logger.debug(
                "Excepted file content for file %s on runner %s: %s\nFound: %s",
                filepath,
                self.instance.name,
                content,
                content_on_runner,
            )
            raise RunnerFileLoadError(
                f"Failed to load file {filepath} to runner {self.instance.name}"
            )

    def _apt_install(self, packages: Iterable[str]) -> None:
        """Installs the given APT packages.

        This is a temporary solution to provide tools not offered by the base ubuntu image. Custom
        images based on the GitHub action runner image will be used in the future.

        Args:
            packages: Packages to be install via apt.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        self.instance.execute(["/usr/bin/apt-get", "update"])

        for pkg in packages:
            logger.info("Installing %s via APT...", pkg)
            self.instance.execute(["/usr/bin/apt-get", "install", "-yq", pkg])

        self.instance.execute(["/usr/bin/apt-get", "clean"])

    def _wget_install(self, executables: Iterable[WgetExecutable]) -> None:
        """Installs the given binaries.

        This is a temporary solution to provide tools not offered by the base ubuntu image. Custom
        images based on the GitHub action runner image will be used in the future.

        Args:
            executables: The executables to download.
        """
        if self.instance is None:
            raise RunnerError("Runner operation called prior to runner creation.")

        for executable in executables:
            executable_path = f"/usr/bin/{executable.cmd}"
            logger.info("Downloading %s via wget to %s...", executable.url, executable_path)
            wget_cmd = ["/usr/bin/wget", executable.url, "-O", executable_path]
            if self.config.proxies.get("http", None) or self.config.proxies.get("https", None):
                wget_cmd += ["-e", "use_proxy=on"]
            if self.config.proxies.get("http", None):
                wget_cmd += ["-e", f"http_proxy={self.config.proxies['http']}"]
            if self.config.proxies.get("https", None):
                wget_cmd += ["-e", f"https_proxy={self.config.proxies['https']}"]
            if self.config.proxies.get("no_proxy", None):
                wget_cmd += ["-e", f"no_proxy={self.config.proxies['no_proxy']}"]
            self.instance.execute(wget_cmd)
            self.instance.execute(["/usr/bin/chmod", "+x", executable_path])
