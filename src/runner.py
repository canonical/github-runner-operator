# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manage the lifecycle of runners.

The `Runner` class stores the information on the runners and manages the
lifecycle of the runners on LXD and GitHub.

The `RunnerManager` class from `runner_manager.py` creates and manages a
collection of `Runner` instances.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError  # nosec B404
from typing import Iterable, Optional, Sequence, TypedDict

import jinja2
import pylxd
import pylxd.models
from ghapi.all import GhApi
from pylxd.exceptions import LXDAPIException

from errors import (
    RunnerCreateError,
    RunnerError,
    RunnerExecutionError,
    RunnerFileLoadError,
    RunnerRemoveError,
)
from runner_type import GitHubOrg, GitHubPath, GitHubRepo, ProxySetting, VirtualMachineResources
from utilities import execute_command, retry

logger = logging.getLogger(__name__)


class LxdInstanceConfigSource(TypedDict):
    """Configuration for source image in LXD instance."""

    type: str
    mode: str
    server: str
    protocol: str
    alias: str


class LxdInstanceConfig(TypedDict):
    """Configuration for LXD instance."""

    name: str
    type: str
    source: LxdInstanceConfigSource
    ephemeral: bool
    profiles: list[str]


@dataclass
class RunnerClients:
    """Clients for access various services.

    Attrs:
        github: Used to query GitHub API.
        jinja: Used for templating.
        lxd: Used to interact with LXD API.
    """

    github: GhApi
    jinja: jinja2.Environment
    lxd: pylxd.Client


@dataclass
class RunnerConfig:
    """Configuration for runner."""

    app_name: str
    path: GitHubPath
    proxies: ProxySetting
    name: str


@dataclass
class RunnerStatus:
    """Status of runner.

    Attrs:
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    exist: bool = False
    online: bool = False
    busy: bool = False


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

    runner_application = Path("/opt/github-runner")
    env_file = runner_application / ".env"
    config_script = runner_application / "config.sh"
    runner_script = runner_application / "start.sh"

    def __init__(
        self,
        clients: RunnerClients,
        runner_config: RunnerConfig,
        runner_status: RunnerStatus,
        instance: Optional[pylxd.models.Instance] = None,
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
            RunnerCreateError: Unable to create a LXD instance for runner.
        """
        logger.info("Creating runner: %s", self.config.name)

        try:
            self.instance = self._create_instance(image, resources)
            self._start_instance()
            # Wait some initial time for the instance to boot up
            time.sleep(60)
            self._wait_boot_up()
            self._install_binary(binary_path)
            self._configure_runner()
            self._register_runner(registration_token, labels=[self.config.app_name, image])
            self._start_runner()
        except (RunnerError, LXDAPIException) as err:
            raise RunnerCreateError(f"Unable to create runner {self.config.name}") from err

    def remove(self, remove_token: str) -> None:
        """Remove this runner instance from LXD and GitHub.

        Args:
            remove_token: Token for removing the runner on GitHub.

        Raises:
            RunnerRemoveError: Failure in removing runner.
        """
        logger.info("Removing LXD instance of runner: %s", self.config.name)

        if self.instance:
            # Run script to remove the the runner and cleanup.
            self._execute(
                [
                    "/usr/bin/sudo",
                    "-u",
                    "ubuntu",
                    str(self.config_script),
                    "remove",
                    "--token",
                    remove_token,
                ],
                check_exit=False,
            )

            if self.instance.status == "Running":
                try:
                    self.instance.stop(wait=True, timeout=60)
                except LXDAPIException:
                    logger.exception(
                        "Unable to gracefully stop runner %s within timeout.", self.config.name
                    )
                    logger.info("Force stopping of runner %s", self.config.name)
                    try:
                        self.instance.stop(force=True)
                    except LXDAPIException as err:
                        raise RunnerRemoveError(f"Unable to remove {self.config.name}") from err

        # The runner should cleanup itself.  Cleanup on GitHub in case of runner cleanup error.
        if isinstance(self.config.path, GitHubRepo):
            self._clients.github.actions.delete_self_hosted_runner_from_repo(
                owner=self.config.path.owner,
                repo=self.config.path.repo,
                runner_id=self.config.name,
            )
        if isinstance(self.config.path, GitHubOrg):
            self._clients.github.actions.delete_self_hosted_runner_from_org(
                org=self.config.path.org, runner_id=self.config.name
            )

    @retry(tries=5, delay=1, local_logger=logger)
    def _create_instance(
        self, image: str, resources: VirtualMachineResources, ephemeral: bool = True
    ) -> pylxd.models.Instance:
        """Create an instance of runner.

        Args:
            image: Image used to launch the instance hosting the runner.
            resources: Configuration of the virtual machine resources.
            ephemeral: Whether the instance is ephemeral.

        Returns:
            LXD instance of the runner.
        """
        logger.info("Creating an LXD instance for runner: %s", self.config.name)

        self._ensure_runner_profile()
        resource_profile = self._get_resource_profile(resources)

        # Create runner instance.
        instance_config: LxdInstanceConfig = {
            "name": self.config.name,
            "type": "virtual-machine",
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

        instance = self._clients.lxd.instances.create(config=instance_config, wait=True)
        self.status.exist = True
        return instance

    @retry(tries=5, delay=1, local_logger=logger)
    def _ensure_runner_profile(self) -> None:
        """Ensure the runner profile is present on LXD.

        Raises:
            RunnerError: Unable to create the runner profile.
        """
        if not self._clients.lxd.profiles.exists("runner"):
            logger.info("Creating runner LXD profile")
            profile_config = {
                "security.nesting": "true",
            }
            self._clients.lxd.profiles.create("runner", profile_config, {})

            # Verify the action is successful.
            if not self._clients.lxd.profiles.exists("runner"):
                raise RunnerError("Failed to create runner LXD profile")
        else:
            logger.info("Found existing runner LXD profile")

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
        profile_name = f"cpu-{resources.cpu}-mem-{resources.memory}-disk-{resources.disk}"
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
                        "pool": "default",
                        "type": "disk",
                        "size": resources.disk,
                    }
                }
                self._clients.lxd.profiles.create(
                    profile_name, resource_profile_config, resource_profile_devices
                )
            except LXDAPIException as error:
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
            return

        logger.info("Starting LXD instance for runner: %s", self.config.name)

        # Setting `wait=True` only ensure the instance has begin to boot up.
        self.instance.start(wait=True)

    @retry(tries=5, delay=30, local_logger=logger)
    def _wait_boot_up(self) -> None:
        # Wait for the instance to finish to boot up and network to be up.
        self._execute(["/usr/bin/who"])
        self._execute(["/usr/bin/nslookup", "github.com"])

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
            return

        # TEMP: Install common tools used in GitHub Actions. This will be removed once virtual
        # machines are created from custom images/GitHub runner image.

        self._apt_install(["docker.io", "npm", "python3-pip", "shellcheck", "jq"])
        self._snap_install(["yq"])

        # Add the user to docker group.
        self._execute(["/usr/sbin/usermod", "-aG", "docker", "ubuntu"])
        self._execute(["/usr/bin/newgrp", "docker"])

        # The LXD instance is meant to run untrusted workload. Hardcoding the tmp directory should
        # be fine.
        binary_path = "/tmp/runner.tgz"  # nosec B108

        logger.info("Installing runner binary on LXD instance: %s", self.config.name)

        # Creating directory and putting the file are idempotent, and can be retried.
        self.instance.files.mk_dir(str(self.runner_application))
        execute_command(
            ["/snap/bin/lxc", "file", "push", str(binary), self.config.name + binary_path]
        )
        self._execute(["/usr/bin/tar", "-xzf", binary_path, "-C", str(self.runner_application)])
        self._execute(["/usr/bin/chown", "-R", "ubuntu:ubuntu", str(self.runner_application)])

        # Verify the env file is written to runner.
        exit_code, _, _ = self.instance.execute(["test", "-f", str(self.config_script)])
        if exit_code == 0:
            logger.info("Runner binary loaded on runner instance %s.", self.config.name)
        else:
            logger.error("Unable to load runner binary on runner instance %s", self.config.name)
            raise RunnerFileLoadError(f"Failed to load runner binary on {self.config.name}")

    @retry(tries=5, delay=1, local_logger=logger)
    def _configure_runner(self) -> None:
        """Load configuration on to the runner.

        Raises:
            RunnerFileLoadError: Unable to load configuration file on the runner.
        """
        if self.instance is None:
            return

        if self.config.proxies:
            logger.info("Adding proxy setting to the runner.")
            env_contents = self._clients.jinja.get_template("env.j2").render(
                proxies=self.config.proxies
            )
            logger.debug("Proxy setting for the runner: %s", env_contents)
            self.instance.files.put(self.env_file, env_contents)
            self._execute(["/usr/bin/chown", "ubuntu:ubuntu", str(self.env_file)])

            docker_proxy_contents = self._clients.jinja.get_template(
                "systemd-docker-proxy.j2"
            ).render(proxies=self.config.proxies)
            self.instance.files.put(
                "/etc/systemd/system/docker.service.d/http-proxy.conf", docker_proxy_contents
            )
            self._execute(["systemctl", "daemon-reload"])
            self._execute(["systemctl", "reload", "docker"])

            # Verify the env file is written to runner.
            exit_code, _, _ = self.instance.execute(["test", "-f", str(self.env_file)])
            if exit_code == 0:
                logger.info("Loaded env file on runner instance %s.", self.config.name)
            else:
                logger.error("Unable to load env file on runner instance %s", self.config.name)
                raise RunnerFileLoadError(f"Failed to load env file on {self.config.name}")

    @retry(tries=5, delay=30, local_logger=logger)
    def _register_runner(self, registration_token: str, labels: Sequence[str]) -> None:
        """Register the runner on GitHub.

        Args:
            registration_token: Registration token request from GitHub.
            labels: Labels to tag the runner with.
        """
        if self.instance is None:
            return

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
            "--name",
            self.instance.name,
            "--unattended",
            "--labels",
            f"{','.join(labels)}",
        ]

        if isinstance(self.config.path, GitHubOrg):
            register_cmd += ["--runnergroup", self.config.path.group]

        self._execute(
            register_cmd,
            cwd=str(self.runner_application),
        )

    @retry(tries=5, delay=30, local_logger=logger)
    def _start_runner(self) -> None:
        """Start the GitHub runner."""
        if self.instance is None:
            return

        logger.info("Starting runner %s", self.config.name)

        # Put a script to run the GitHub self-hosted runner in the instance and run it.
        contents = self._clients.jinja.get_template("start.j2").render()
        self.instance.files.put(self.runner_script, contents, mode="0755")
        self._execute(["/usr/bin/sudo", "chown", "ubuntu:ubuntu", str(self.runner_script)])
        self._execute(["/usr/bin/sudo", "chmod", "u+x", str(self.runner_script)])
        self._execute(
            [
                "/usr/bin/sudo",
                "-u",
                "ubuntu",
                (
                    "PATH=/home/ubuntu/.local/bin"
                    ":/usr/local/sbin"
                    ":/usr/local/bin"
                    ":/usr/sbin"
                    ":/usr/bin"
                    ":/sbin"
                    ":/bin"
                    ":/snap/bin"
                ),
                str(self.runner_script),
            ]
        )

        logger.info("Started runner %s", self.config.name)

    def _execute(
        self, cmd: list[str], cwd: Optional[str] = None, check_exit: bool = True, **kwargs
    ) -> str:
        """Check execution of a command in a LXD instance.

        The command is executed with `subprocess.run`, additional arguments can be passed to it as
        keyword arguments. The following arguments to `subprocess.run` should not be set:
        `capture_output`, `shell`, `check`. As those arguments are used by this function.

        Args:
            instance: LXD instance of the runner.
            cmd: Sequence of command to execute on the runner.
            cwd: Working directory to execute the command.
            check_exit: Whether to check for non-zero exit code and raise exceptions.
            kwargs: Additional keyword arguments for the `subprocess.run` call.

        Returns:
            The stdout of the command executed.
        """
        if self.instance is None:
            raise RunnerExecutionError(
                f"{self.config.name} is missing LXD instance to execute command {cmd}"
            )

        lxc_exec_cmd = ["/snap/bin/lxc", "exec", self.instance.name]
        if cwd is not None:
            lxc_exec_cmd += ["--cwd", cwd]

        lxc_exec_cmd += ["--"] + cmd

        try:
            return execute_command(lxc_exec_cmd, check_exit, **kwargs)
        except CalledProcessError as err:
            raise RunnerExecutionError(
                f"Failed to execute command in {self.config.name}: {cmd}"
            ) from err

    def _apt_install(self, packages: Iterable[str]) -> None:
        """Installs the given APT packages.

        This is a temporary solution to provide tools not offered by the base ubuntu image. Custom
        images based on the GitHub action runner image will be used in the future.

        Args:
            packages: Packages to be install via apt.
        """
        self._execute(["/usr/bin/apt-get", "update"])

        for pkg in packages:
            logger.info("Installing %s via APT...", pkg)
            self._execute(["/usr/bin/apt-get", "install", "-yq", pkg])

    def _snap_install(self, packages: Iterable[str]) -> None:
        """Installs the given snap packages.

        This is a temporary solution to provide tools not offered by the base ubuntu image. Custom
        images based on the GitHub action runner image will be used in the future.

        Args:
            packages: Packages to be install via snap.
        """
        for pkg in packages:
            logger.info("Installing %s via snap...", pkg)
            self._execute(["/usr/bin/snap", "install", pkg])
