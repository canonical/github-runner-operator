# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manage the dependencies and lifecycle of runners."""

import logging
from pathlib import Path
from typing import List, Optional, Sequence, TypedDict

import jinja2
import pylxd
import pylxd.exceptions
import pylxd.models
from ghapi.all import GhApi

from errors import RunnerError, RunnerExecutionError, RunnerFileLoadError, RunnerRemoveError
from retry import retry
from runner_type import GitHubPath, ProxySetting, VirtualMachineResources

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

    runner_application = Path("/opt/github-runner")
    env_file = runner_application / ".env"
    config_script = runner_application / "config.sh"
    runner_script = runner_application / "start.sh"

    def __init__(
        self,
        github: GhApi,
        jinja: jinja2.Environment,
        lxd: pylxd.Client,
        path: GitHubPath,
        app_name: str,
        binary_path: Path,
        name: str,
        image: str,
        resources: Optional[VirtualMachineResources],
        proxies: ProxySetting,
        reconcile_interval: int,
        registration_token: str,
    ):
        # Dependency injection to share the instances across different `Runner` instance.
        self._github = github
        self._jinja = jinja
        self._lxd = lxd

        self.path = path
        self.app_name = app_name
        self.binary_path = binary_path
        self.name = name
        self.image = image
        self.resources = resources
        self.proxies = proxies
        self.reconcile_interval = reconcile_interval
        self.registration_token = registration_token

        self.instance = None

    def create(self):
        self.instance = self._create_instance(image=self.image, resources=self.resources)

        try:
            self._start_instance()
            self._install_binary()
            self._configure_runner()
            self._register_runner(self.registration_token, labels=[self.app_name, self.image])
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

    @retry(tries=10, delay=5, max_delay=60, backoff=1.5, logger=logger)
    def remove(self) -> None:
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
        return self._lxd.instances.create(config=instance_config, wait=True)

    def _ensure_runner_profile(self) -> None:
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

    def _get_resource_profile(self, resources: VirtualMachineResources) -> str:

        # Ensure the resource profile exists.
        profile_name = f"cpu-{resources.cpu}-mem-{resources.memory}-disk-{resources.disk}"
        if not self._lxd.profiles.exists(profile_name):
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

        return profile_name

    def _start_instance(self) -> None:
        """Start an instance and wait for it to boot.

        Args:
            instance: LXD instance of the runner.
        """
        assert self.instance is not None

        wait_interval = 15  # seconds
        attempts = int(self.reconcile_interval * 60 / wait_interval)

        @retry(exception=RunnerExecutionError, tries=attempts, delay=wait_interval, logger=logger)
        def connect_test():
            self._check_output(["ping", "-q", "-c1", "github.com"])

        self.instance.start(wait=True)

        # Wait for the instance to boot
        connect_test()

    @retry(tries=10, delay=1, logger=logger)
    def _install_binary(self) -> None:
        if self.instance is None:
            return

        binary_path = "/tmp/runner.tgz"

        logger.info("Installing runner binary on LXD instance.")
        # Create directory idempotent, and can be retried.
        self.instance.files.mk_dir(str(self.runner_application))
        self.instance.files.put(binary_path, self.binary_path.read_bytes())
        self._check_output(["chown", "-R", "ubuntu:ubuntu", str(self.runner_application)])

        # Verify the env file is written to runner.
        exit_code, _, _ = self.instance.execute(["test", "-f", str(self.config_script)])
        if exit_code == 0:
            logger.info("Runner binary loaded on runner instance %s.", self.name)
        else:
            logger.error("Unable to load runner binary on runner instance %s", self.name)
            raise RunnerFileLoadError(f"Failed to load runner binary on {self.name}")

    @retry(tries=10, delay=1, logger=logger)
    def _configure_runner(self) -> None:
        if self.instance is None:
            return

        if self.proxies:
            contents = self._jinja.get_template("env.j2").render(proxies=self.proxies)
            self.instance.files.put(self.env_file, contents, mode="0600")
            self._check_output(["chown", "ubuntu:ubuntu", str(self.env_file)])

            # Verify the env file is written to runner.
            exit_code, _, _ = self.instance.execute(["test", "-f", str(self.env_file)])
            if exit_code == 0:
                logger.info("Env file loaded on runner instance %s.", self.name)
            else:
                logger.error("Unable to load env file on runner instance %s", self.name)
                raise RunnerFileLoadError(f"Failed to load env file on {self.name}")

    def _register_runner(self, registration_token: str, labels: Sequence[str]) -> None:
        self._check_output(
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

    def _start_runner(self) -> None:
        if self.instance is None:
            return

        contents = self._jinja.get_template("start.js").render()
        self.instance.files.put(self.runner_script, contents, mode="0755")
        self._check_output(["sudo", "-u", "ubuntu:ubuntu", str(self.runner_script)])
        self._check_output(["sudo", "chmod", "u+x", str(self.runner_script)])
        self._check_output(["sudo", "-u", "ubuntu", str(self.runner_script)])

    def _check_output(self, cmd: List[str]) -> str:
        """Check execution of a command in a LXD instance.

        Args:
            instance: LXD instance of the runner.
            cmd: Sequence of command to execute on the runner.

        Returns:
            The stdout of the command executed.
        """
        assert self.instance is not None

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
