# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manage the dependencies and lifecycle of runners."""

import logging
import time
from pathlib import Path
from typing import List, Optional, Sequence, TypedDict

import jinja2
import pylxd
import pylxd.exceptions
import pylxd.models
from ghapi.all import GhApi

from errors import (
    RunnerCreateError,
    RunnerError,
    RunnerExecutionError,
    RunnerFileLoadError,
    RunnerRemoveError,
)
from runner_type import GitHubOrg, GitHubPath, GitHubRepo, ProxySetting, VirtualMachineResources
from utilities import retry

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
    profiles: List[str]


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
        github: GhApi,
        jinja: jinja2.Environment,
        lxd: pylxd.Client,
        app_name: str,
        path: GitHubPath,
        proxies: ProxySetting,
        name: str,
        exist: bool = False,
        online: bool = False,
        busy: bool = False,
        instance: Optional[pylxd.models.Instance] = None,
    ):
        """Construct the runner instance.

        Args:
            github: Used to query GitHub API.
            jinja: Used for working with template.
            lxd: Used to interact with LXD API.
            app_name: Name of the charm.
            path: Path to GitHub repo or org.
            proxies: HTTP proxy setting for juju charm.
            name: Name of the runner.
            exist: Whether the runner instance exists on LXD. Defaults to False.
            online: Whether GitHub marks this runner as online. Defaults to False.
            busy: Whether GitHub marks this runner as busy. Defaults to False.
            instance: LXD instance of the runner if already created. Defaults to None.
        """
        # Dependency injection to share the instances across different `Runner` instance.
        self._github = github
        self._jinja = jinja
        self._lxd = lxd

        self.app_name = app_name
        self.path = path
        self.proxies = proxies

        self.name = name
        self.exist = exist
        self.online = online
        self.busy = busy

        self.instance = instance

    def create(
        self,
        image: str,
        resources: VirtualMachineResources,
        binary: Path,
        reconcile_interval: int,
        registration_token: str,
    ):
        logger.info("Creating runner: %s", self.name)

        self.instance = self._create_instance(image, resources)

        try:
            self._start_instance(reconcile_interval)
            self._install_binary(binary)
            self._configure_runner()
            self._register_runner(registration_token, labels=[self.app_name, image])
            self._start_runner()
        except Exception as err:
            self.instance.stop(wait=True)
            try:
                self.instance.delete(wait=True)
            except Exception:  # nosec B110
                # this is just a fall-back.
                # Ephemeral containers should auto-delete when stopped;
                pass
            raise RunnerCreateError(str(err)) from err

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5, logger=logger)
    def remove(self) -> None:
        """Remove this runner instance from LXD and GitHub.

        Raises:
            RunnerRemoveError: Failure in removing runner.
        """

        @retry(tries=10, delay=10, logger=logger)
        def check_shutdown():
            instance = self._lxd.instances.get(self.name)
            if instance.status != "Stopped":
                raise RunnerRemoveError(f"Unable to stop LXD instance for runner {self.name}")

        logger.info("Removing LXD instance for runner: %s", self.name)

        if isinstance(self.path, GitHubRepo):
            self._github.actions.delete_self_hosted_runner_from_repo(
                owner=self.path.owner, repo=self.path.repo, runner_id=self.name
            )
        elif isinstance(self.path, GitHubOrg):
            self._github.actions.delete_self_hosted_runner_from_org(
                org=self.path.org, runner_id=self.name
            )

        if self.instance is None:
            return

        if self.instance.status == "Running":
            self.instance.stop(wait=True)
            time.sleep(30)

            check_shutdown()

            try:
                self.instance.delete(wait=True)
            except Exception:  # nosec B110
                # Ephemeral containers should auto-delete when stopped;
                # this is just a fall-back.
                pass
        else:
            # We somehow have a non-running instance which should have been
            # ephemeral. Try to delete it and allow any errors doing so to
            # surface.
            try:
                self.instance.delete(wait=True)
            except Exception as err:
                raise RunnerRemoveError() from err

    @retry(tries=10, delay=1, logger=logger)
    def _create_instance(
        self, image: str, resources: VirtualMachineResources, ephemeral: bool = True
    ) -> pylxd.models.Instance:
        """Create a instance of runner.

        Args:
            image: Image to launch the instance hosting the runner.
            resources: Configuration of the virtual machine resources.
            ephemeral: Whether the instance is ephemeral. Defaults to True.

        Returns:
            LXD instance of the runner.
        """
        logger.info("Creating an LXD instance for runner: %s", self.name)

        self._ensure_runner_profile()
        resource_profile = self._get_resource_profile(resources)

        # Create runner instance.
        instance_config: LxdInstanceConfig = {
            "name": self.name,
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

        instance = self._lxd.instances.create(config=instance_config, wait=True)
        self.exist = True
        return instance

    @retry(tries=10, delay=1, logger=logger)
    def _ensure_runner_profile(self) -> None:
        """Ensure the runner profile is present on LXD.

        Raises:
            RunnerError: Unable to create the runner profile.
        """
        if not self._lxd.profiles.exists("runner"):
            logger.info("Creating runner LXD profile")
            profile_config = {
                "security.nesting": "true",
                "security.privileged": "true",
            }
            self._lxd.profiles.create("runner", profile_config, {})

            # Verify the action is successful.
            if not self._lxd.profiles.exists("runner"):
                raise RunnerError("Failed to create runner LXD profile")
        else:
            logger.info("Found existing runner LXD profile")

    @retry(tries=10, delay=1, logger=logger)
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
        if not self._lxd.profiles.exists(profile_name):
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
                self._lxd.profiles.create(
                    profile_name, resource_profile_config, resource_profile_devices
                )
            except pylxd.exceptions.LXDAPIException as error:
                logger.error(error)
                raise RunnerError(
                    "Resources were not provided in the correct format, check the juju config for "
                    "cpu, memory and disk."
                ) from error

            # Verify the action is successful.
            if not self._lxd.profiles.exists(profile_name):
                raise RunnerError(f"Unable to create {profile_name} LXD profile")
        else:
            logger.info("Found existing LXD profile for resource usage.")

        return profile_name

    @retry(tries=10, delay=1, logger=logger)
    def _start_instance(self, reconcile_interval) -> None:
        """Start an instance and wait for it to boot.

        Args:
            reconcile_interval: Time in seconds of period between each reconciliation.
        """
        if self.instance is None:
            return

        logger.info("Starting LXD instance for runner: %s", self.name)

        wait_interval = 15  # seconds
        attempts = int(reconcile_interval * 60 / wait_interval)

        @retry(exception=RunnerExecutionError, tries=attempts, delay=wait_interval, logger=logger)
        def connect_test():
            """Check able to connect to network."""
            try:
                self._execute(["/usr/bin/who"])
                # TODO Better network test? Ping `github.com` too much results in throttling.
                self._execute(["/usr/bin/ping", "-q", "-c1", "ubuntu.com"])
            except BrokenPipeError as err:
                raise RunnerExecutionError(str(err)) from err

        # Setting `wait=True` only ensure the instance has begin to boot up.
        self.instance.start(wait=True)
        # Wait some initial time for the instance to boot up
        time.sleep(60)

        # Wait for the instance to finish to boot up. The network should be up.
        connect_test()

        logger.info("Finished booting up LXD instance for runner: %s", self.name)

    @retry(tries=10, delay=1, logger=logger)
    def _install_binary(self, binary: Path) -> None:
        """Load GitHub self-hosted runner binary on to the runner instance.

        Args:
            binary: Path the compressed runner binary.

        Raises:
            RunnerFileLoadError: Unable to load the file into the runner instance.
        """
        if self.instance is None:
            return

        # The LXD instance is meant to run untrusted workload. Hardcoding the tmp directory should
        # be fine.
        binary_path = "/tmp/runner.tgz"  # nosec B108

        logger.info("Installing runner binary on LXD instance: %s", self.name)

        # Creating directory and putting the file are idempotent, and can be retried.
        self.instance.files.mk_dir(str(self.runner_application))
        self.instance.files.put(binary_path, binary.read_bytes())
        self._execute(["tar", "-xzf", binary_path, "-C", str(self.runner_application)])
        self._execute(["chown", "-R", "ubuntu:ubuntu", str(self.runner_application)])

        # Verify the env file is written to runner.
        exit_code, _, _ = self.instance.execute(["test", "-f", str(self.config_script)])
        if exit_code == 0:
            logger.info("Runner binary loaded on runner instance %s.", self.name)
        else:
            logger.error("Unable to load runner binary on runner instance %s", self.name)
            raise RunnerFileLoadError(f"Failed to load runner binary on {self.name}")

    @retry(tries=10, delay=1, logger=logger)
    def _configure_runner(self) -> None:
        """Load configuration on to the runner.

        Raises:
            RunnerFileLoadError: Unable to load configuration file on the runner.
        """

        if self.instance is None:
            return

        if self.proxies:
            contents = self._jinja.get_template("env.j2").render(proxies=self.proxies)
            self.instance.files.put(self.env_file, contents, mode="0600")
            self._execute(["chown", "ubuntu:ubuntu", str(self.env_file)])

            # Verify the env file is written to runner.
            exit_code, _, _ = self.instance.execute(["test", "-f", str(self.env_file)])
            if exit_code == 0:
                logger.info("Loaded env file on runner instance %s.", self.name)
            else:
                logger.error("Unable to load env file on runner instance %s", self.name)
                raise RunnerFileLoadError(f"Failed to load env file on {self.name}")

    @retry(tries=10, delay=1, logger=logger)
    def _register_runner(self, registration_token: str, labels: Sequence[str]) -> None:
        """Register the runner on GitHub.

        Args:
            registration_token: Registration token request from GitHub.
            labels: Labels to tag the runner with.
        """
        logger.info("Registering runner %s", self.name)

        self._execute(
            [
                "sudo",
                "-u",
                "ubuntu",
                str(self.config_script),
                f"--url https://github.com/{self.path.path()}",
                "--token",
                f"{registration_token}",
                "--ephemeral",
                "--name",
                f"instance.name",
                "--unattended",
                "--labels",
                f"{','.join(labels)}",
            ]
        )

    @retry(tries=10, delay=1, logger=logger)
    def _start_runner(self) -> None:
        """Start the GitHub runner."""

        if self.instance is None:
            return

        logger.info("Starting runner %s", self.name)

        # Put a script to run the GitHub self-hosted runner in the instance and run it.
        contents = self._jinja.get_template("start.js").render()
        self.instance.files.put(self.runner_script, contents, mode="0755")
        self._execute(["sudo", "-u", "ubuntu:ubuntu", str(self.runner_script)])
        self._execute(["sudo", "chmod", "u+x", str(self.runner_script)])
        self._execute(["sudo", "-u", "ubuntu", str(self.runner_script)])

        logger.info("Started runner %s", self.name)

    def _execute(self, cmd: List[str]) -> str:
        """Check execution of a command in a LXD instance.

        Args:
            instance: LXD instance of the runner.
            cmd: Sequence of command to execute on the runner.

        Returns:
            The stdout of the command executed.
        """
        if self.instance is None:
            raise RunnerExecutionError(
                f"{self.name} is missing LXD instance to execute command {cmd}"
            )

        exit_code, stdout, stderr = self.instance.execute(cmd)
        if exit_code == 0:
            logger.debug("%s executed %s with exit code: %i", self.name, cmd, exit_code)
            logger.debug("%s executed %s with stdout: %s", self.name, cmd, stdout)
            logger.debug("%s executed %s with stderr: %s", self.name, cmd, stderr)
        else:
            logger.error("%s executed %s with exit code: %i", self.name, cmd, exit_code)
            logger.error("%s executed %s with stdout: %s", self.name, cmd, stdout)
            logger.error("%s executed %s with stderr: %s", self.name, cmd, stderr)
            raise RunnerExecutionError(f"{self.name} executed {cmd} with exit code {exit_code}")

        return stdout
