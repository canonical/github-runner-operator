#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""RunnerManager for managing the dependencies and lifecycle of runners.

TODO:
Create a Runner class. This splits the logic within the RunnerManager into smaller pieces
of methods. It should be easier to test as well. The RunnerManager class will have the logic
of managing a list of runners. The Runner class will have the logic of interacting with runner
and query runner info.

Also enforce the local and remote info through type design. E.g., if Runner cannot be
neither local and remote at the same time, enforce it through type design.
Why:
* Impossible to create runner info that is neither local and remote. This
is allowed by current design.
* Type-driven design works better with type checkers. Search for "mypy" in comment for add code
needed for type checker under current-design.
"""


import logging
import os
import subprocess  # nosec B404
import time
import urllib.error
import urllib.request
from pathlib import Path
from random import choices
from string import ascii_lowercase, digits
from typing import List, NamedTuple, Optional, Sequence, TypedDict

import fastcore.net
import pylxd
import pylxd.models
import requests
from ghapi.all import GhApi
from jinja2 import Environment, FileSystemLoader
from pylxd.exceptions import LXDAPIException, NotFound

logger = logging.getLogger(__name__)


class VMResources(NamedTuple):
    """Virtual machine resource configuration."""

    cpu: int
    memory: str
    disk: str


class RunnerLabel(TypedDict):
    """Label in GitHub API for runner status."""

    id: int
    name: str
    type: type


class RemoteRunner(TypedDict):
    """Runner information in GitHub API."""

    id: int
    busy: bool
    status: str
    labels: List[RunnerLabel]


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


class RunnerInfo:
    """RunnerInfo stores the info on a runner.

    Attributes:
        name (str): Name of the runner.
        local (pylxd.models.Instance): Local LXD instance information of runner.
        remote (RemoteRunner): GitHub API information of runner.
    """

    def __init__(
        self, name: str, local: Optional[pylxd.models.Instance], remote: Optional[RemoteRunner]
    ) -> None:
        """Construct a instance of runner information.

        Args:
            name: Name of the runner.
            local: Local LXD instance information of runner.
            remote: GitHub API information of runner.
        """
        self.name = name
        self.local = local
        self.remote = remote

    @property
    def is_idle(self) -> bool:
        """Whether the runner is idle.

        Returns:
            Whether the runner is idle.
        """
        # Redundant None check for mypy type check.
        return self.is_online and self.remote is not None and self.remote["busy"] is False

    @property
    def is_offline(self) -> bool:
        """Whether the runner is offline.

        Returns:
            Whether the runner is offline.
        """
        return self.remote is not None and self.remote["status"] != "online"

    @property
    def is_online(self) -> bool:
        """Whether the runner is online.

        Returns:
            Whether the runner is online.
        """
        return self.remote is not None and self.remote["status"] == "online"

    @property
    def is_local(self) -> bool:
        """Whether the runner is local.

        Returns:
            Whether the runner is local.
        """
        return self.local is not None

    @property
    def virt_type(self) -> Optional[str]:
        """Return the virtualization type of the runner.

        Returns:
            Virtualization type of the runner.
        """
        if self.is_local:
            # Assert for mypy type check. This check is already done by `is_local`.
            assert self.local is not None  # nosec B101
            return self.local.type
        elif self.remote:
            remote_virt_type = (
                label["name"]
                for label in self.remote["labels"]
                if label["name"] in {"container", "virtual-machine"}
            )
            return next(remote_virt_type, None)
        return None


class RunnerError(Exception):
    """Generic runner error."""


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class RunnerRemoveError(RunnerError):
    """Error for runner removal failure."""


class RunnerStartError(RunnerError):
    """Error for runner start failure."""


class RunnerManager:
    """Class for querying and controlling the runners.

    Attributes:
        proxies (Dict[str, str]): Mapping of proxy env vars.
        path (str): GitHub repository path in the format '<org>/<repo>', or the GitHub org name.
        app_name (str): An name for the set of runners.
        reconcile_interval (int): Number of minutes between each reconciliation of runners state.
    """

    # TODO: Verify if this violates bandit B108.
    runner_bin_path = Path("/var/cache/github-runner-operator/runner.tgz")
    env_file = Path("/opt/github-runner/.env")

    def __init__(self, path: str, token: str, app_name: str, reconcile_interval: int) -> None:
        """Construct RunnerManager object for creating and managing runners.

        Args:
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name.
            token: GitHub personal access token to register runner to the repository or
                organization.
            app_name: An name for the set of runners.
            reconcile_interval: Number of minutes between each reconciliation of runners.
        """
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY", None)
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY", None)
        no_proxy = os.environ.get("JUJU_CHARM_NO_PROXY", None)
        self.proxies = {}
        if http_proxy:
            self.proxies["http"] = http_proxy
        if https_proxy:
            self.proxies["https"] = https_proxy
        if no_proxy:
            self.proxies["no_proxy"] = no_proxy
        self.session = requests.Session()
        if self.proxies:
            # setup proxy for requests
            self.session.proxies.update(self.proxies)
            # add proxy to fastcore which ghapi uses
            proxy = urllib.request.ProxyHandler(self.proxies)
            opener = urllib.request.build_opener(proxy)
            fastcore.net._opener = opener
        self._jinja = Environment(loader=FileSystemLoader("templates"), autoescape=True)
        self._lxd = pylxd.Client()
        self.path = path
        self._api = GhApi(token=token)
        self.app_name = app_name
        self.reconcile_interval = reconcile_interval

    @classmethod
    def install_deps(cls) -> None:
        """Install dependencies."""
        # Binding for snap, apt, and lxd init commands are not available so subprocess.run used.
        subprocess.run(["/usr/bin/snap", "install", "lxd"], check=True)  # nosec 603
        subprocess.run(["/snap/bin/lxd", "init", "--auto"], check=True)  # nosec 603
        subprocess.run(  # nosec B603
            [
                "/usr/bin/apt",
                "install",
                "-qy",
                "cpu-checker",
                "libvirt-clients",
                "libvirt-daemon-driver-qemu",
            ],
            check=True,
        )
        cls.runner_bin_path.parent.mkdir(parents=True, exist_ok=True)

    def get_latest_runner_bin_url(self) -> Optional[str]:
        """Get the URL for the latest runner binary.

        Returns:
            URL to download the runner binary.
        """
        # TODO: make these not hard-coded
        os_name = "linux"
        arch_name = "x64"

        if "/" in self.path:
            owner, repo = self.path.split("/")
            runner_bins = self._api.actions.list_runner_applications_for_repo(
                owner=owner, repo=repo
            )
        else:
            runner_bins = self._api.actions.list_runner_applications_for_org(org=self.path)
        for runner_bin in runner_bins:
            if runner_bin.os == os_name and runner_bin.architecture == arch_name:
                return runner_bin.download_url
        return None

    def update_runner_bin(self, download_url: str) -> None:
        """Download a runner file, replacing the current copy.

        Args:
            download_url (str): URL to download the runner binary.
        """
        # Remove any existing runner bin file
        if self.runner_bin_path.exists():
            self.runner_bin_path.unlink()
        # Download the new file
        response = self.session.get(download_url)
        with self.runner_bin_path.open(mode="wb") as runner_bin_file:
            runner_bin_file.write(response.content)

    def get_info(self) -> List[RunnerInfo]:
        """Return a list of RunnerInfo objects.

        Returns:
            List of information on the runners.
        """
        local_runners = {
            c.name: c for c in self._lxd.instances.all() if c.name.startswith(f"{self.app_name}-")
        }
        if "/" in self.path:
            owner, repo = self.path.split("/")
            remote_runners = self._api.actions.list_self_hosted_runners_for_repo(
                owner=owner, repo=repo
            )["runners"]
        else:
            remote_runners = self._api.actions.list_self_hosted_runners_for_org(org=self.path)[
                "runners"
            ]
        remote_runners = {
            r.name: r for r in remote_runners if r.name.startswith(f"{self.app_name}-")
        }
        runners = []
        for name in set(local_runners.keys()) | set(remote_runners.keys()):
            runners.append(RunnerInfo(name, local_runners.get(name), remote_runners.get(name)))
        return runners

    def reconcile(
        self, virt_type: str, quantity: int, vm_resources: Optional[VMResources] = None
    ) -> int:
        """Bring runners in line with target.

        Args:
            virt_type: Virtualization type of the runner to reconcile.
            quantity: Number of intended runners.
            vm_resources: Configuration of the virtual machine resources.

        Returns:
            Difference between intended runners and actual runners.
        """
        runners = [r for r in self.get_info() if r.virt_type == virt_type]

        # Clean up offline runners
        offline_runners = [r for r in runners if r.is_offline]
        if offline_runners:
            runner_names = ", ".join(r.name for r in offline_runners)
            logger.info(f"Cleaning up offline {virt_type} runners: {runner_names}")
            for runner in offline_runners:
                self._remove_runner(runner)

        # Add/Remove runners to match the target quantity
        local_online_runners = [r for r in runners if r.is_online and r.is_local]
        delta = quantity - len(local_online_runners)
        if delta > 0:
            logger.info(f"Adding {delta} additional {virt_type} runner(s)")
            for i in range(delta):
                self.create(image="ubuntu", virt=virt_type, vm_resources=vm_resources)

        if delta < 0:
            local_idle_runners = [r for r in local_online_runners if r.is_idle]
            # The `local_idle_runners` are filter for only local runners
            # The if-else statement is for mypy type check.
            local_idle_runners.sort(
                key=lambda r: r.local.created_at if r.local is not None else False
            )
            offset = min(abs(delta), len(local_idle_runners))
            if offset == 0:
                logger.info(f"There are no idle {virt_type} runners to remove.")
            else:
                old_runners = local_online_runners[:offset]
                runner_names = ", ".join(r.name for r in old_runners)
                logger.info(f"Removing extra {offset} idle {virt_type} runner(s): {runner_names}")
                for runner in old_runners:
                    self._remove_runner(runner)

        return delta

    def clear(self) -> None:
        """Clear out existing local runners."""
        runners = [r for r in self.get_info() if r.is_local]
        runner_names = ", ".join(r.name for r in runners)
        logger.info(f"Removing existing local runners: {runner_names}")
        for runner in runners:
            self._remove_runner(runner)

        self._clean_unused_profiles()

    def create(
        self, image: str, virt: str = "container", vm_resources: Optional[VMResources] = None
    ) -> None:
        """Create a runner.

        Args:
            image: Image to launch the runner with.
            virt: Virtualization type of the runner.
            vm_resources: Configuration of the virtual machine resources.
        """
        instance = self._create_instance(image=image, virt=virt, vm_resources=vm_resources)

        try:
            self._start_instance(instance)
            self._install_binary(instance)
            self._configure_runner(instance)
            self._register_runner(
                instance,
                labels=[
                    self.app_name,
                    image,
                    virt,
                ],
            )
            self._start_runner(instance)
            if virt == "container":
                self._load_aaprofile(instance)
        except Exception as e:
            instance.stop(wait=True)
            try:
                instance.delete(wait=True)
            except Exception:  # nosec B110
                # this is just a fall-back.
                # Ephemeral containers should auto-delete when stopped;
                pass
            raise RunnerCreateError(str(e)) from e

    def _remove_runner(self, runner: RunnerInfo) -> None:
        """Remove a runner.

        Args:
            runner: Information on the runner to remove.
        """
        if runner.remote:
            try:
                if "/" in self.path:
                    owner, repo = self.path.split("/")
                    self._api.actions.delete_self_hosted_runner_from_repo(
                        owner=owner, repo=repo, runner_id=runner.remote["id"]
                    )
                else:
                    self._api.actions.delete_self_hosted_runner_from_org(
                        org=self.path, runner_id=runner.remote["id"]
                    )
            except Exception as e:
                raise RunnerRemoveError(f"Failed remove remote runner: {runner.name}") from e

        if runner.local:
            try:
                if runner.local.status == "Running":
                    runner.local.stop(wait=True)
                    try:
                        runner.local.delete(wait=True)
                    except Exception:  # nosec B110
                        # Ephemeral containers should auto-delete when stopped;
                        # this is just a fall-back.
                        pass
                else:
                    # We somehow have a non-running instance which should have been
                    # ephemeral. Try to delete it and allow any errors doing so to
                    # surface.
                    runner.local.delete(wait=True)
            except Exception as e:
                raise RunnerRemoveError(f"Failed remove local runner: {runner.name}") from e

        # remove profile
        try:
            profile = self._lxd.profiles.get(runner.name)
            profile.delete()
        except (LXDAPIException, NotFound):
            pass

    def _clean_unused_profiles(self) -> None:
        """Clean all unused profiles created with this manager."""
        for profile in self._lxd.profiles.all():
            if profile.name.startswith(self.app_name) and not profile.used_by:
                profile.delete()

    def _register_runner(self, instance: pylxd.models.Instance, labels: Sequence[str]) -> None:
        """Register a runner in an instance.

        Args:
            instance: LXD instance of the runner.
            labels: Sequence of labels to tag the runner with.
        """
        api = self._api
        if "/" in self.path:
            owner, repo = self.path.split("/")
            token = api.actions.create_registration_token_for_repo(owner=owner, repo=repo)
        else:
            token = api.actions.create_registration_token_for_org(org=self.path)
        cmd = [
            "sudo -u ubuntu /opt/github-runner/config.sh",
            f"--url https://github.com/{self.path} ",
            "--token ",
            f"{token.token} ",
            "--ephemeral ",
            "--name ",
            f"{instance.name} ",
            "--unattended ",
            "--labels ",
            f"{','.join(labels)}",
        ]
        self._check_output(instance, cmd)

    def _start_runner(self, instance: pylxd.models.Instance) -> None:
        """Start a runner that is already registered.

        Args:
            instance: LXD instance of the runner.
        """
        script_contents = self._jinja.get_template("start.j2").render()
        instance.files.put("/opt/github-runner/start.sh", script_contents, mode="0755")
        self._check_output(
            instance, "sudo chown ubuntu:ubuntu /opt/github-runner/start.sh".split()
        )
        self._check_output(instance, "sudo chmod u+x /opt/github-runner/start.sh".split())
        self._check_output(instance, "sudo -u ubuntu /opt/github-runner/start.sh".split())

    def _load_aaprofile(self, instance: pylxd.models.Instance) -> None:
        """Load the apparmor profile so classic snaps can run.

        Args:
            instance: LXD instance of the runner.
        """
        self._check_output(
            instance,
            ["bash", "-c", "sudo apparmor_parser -r /etc/apparmor.d/*snap-confine*"],
        )
        cmd = [
            "bash",
            "-c",
            "sudo apparmor_parser /var/lib/snapd/apparmor/profiles/snap-confine*",
        ]
        exit_code, stdout, stderr = instance.execute(cmd)
        logger.info(f"Apparmor exit_code: {exit_code}")
        logger.info(f"Apparmor stdout: {stdout}")
        logger.info(f"Apparmor stderr: {stderr}")

    def _configure_runner(self, instance: pylxd.models.Instance) -> None:
        """Configure the runner.

        Args:
            instance: LXD instance of the runner.
        """
        # Render proxies if configured
        if self.proxies:
            contents = self._jinja.get_template("env.j2").render(proxies=self.proxies)
            instance.files.put(self.env_file, contents, mode="0600")
            self._check_output(instance, "chown ubuntu:ubuntu /opt/github-runner/.env".split())

    def _install_binary(self, instance: pylxd.models.Instance) -> None:
        """Install the binary in a instance.

        Args:
            instance: LXD instance of the runner.
        """
        instance.files.mk_dir("/opt/github-runner")
        for attempt in range(10):
            try:
                # The LXD instance is meant to run untrusted workload, using hardcoded tmp
                # directory should be fine.
                instance.files.put(
                    "/tmp/runner.tgz", self.runner_bin_path.read_bytes()  # nosec B108
                )
                self._check_output(
                    instance, "tar -xzf /tmp/runner.tgz -C /opt/github-runner".split()
                )
                self._check_output(instance, "chown -R ubuntu:ubuntu /opt/github-runner".split())
                break
            except subprocess.CalledProcessError:
                if attempt < 9:
                    logger.warning("Failed to install runner, trying again")
                    time.sleep(0.5)
                else:
                    logger.error("Failed to install runner, giving up")
                    raise

    def _check_output(self, container: pylxd.models.Instance, cmd: List[str]) -> str:
        """Check execution of a command in a container.

        Args:
            instance: LXD instance of the runner.
            cmd: Sequence of command to execute on the runner.
        """
        exit_code, stdout, stderr = container.execute(cmd)
        logger.debug(f"Exit code {exit_code} from {cmd}")
        subprocess.CompletedProcess(cmd, exit_code, stdout, stderr).check_returncode()
        return stdout

    def _create_instance(
        self,
        image: str = "focal",
        virt: str = "container",
        vm_resources: Optional[VMResources] = None,
    ) -> pylxd.models.Instance:
        """Create a instance of runner.

        Args:
            image: Image to launch the runner. Defaults to "focal".
            virt: Virtualization type of the runner. Defaults to "container".
            vm_resources: Configuration of the virtual machine resources. Defaults to None.

        Returns:
            LXD instance of the runner.
        """
        if virt == "container" and vm_resources is not None:
            logger.warning("vm resources should be use only with virtual-machine")

        # Generated a suffix for naming propose, not used as secret.
        suffix = "".join(choices(ascii_lowercase + digits, k=6))  # nosec B311
        name = f"{self.app_name}-{suffix}"
        if not self._lxd.profiles.exists("runner"):
            profile_config = {
                "security.nesting": "true",
                "security.privileged": "true",
            }
            self._lxd.profiles.create("runner", profile_config, {})

        instance_config: LxdInstanceConfig = {
            "name": name,
            "type": virt,
            "source": {
                "type": "image",
                "mode": "pull",
                "server": "https://cloud-images.ubuntu.com/daily",
                "protocol": "simplestreams",
                "alias": image,
            },
            "ephemeral": True,
            "profiles": ["default", "runner"],
        }
        # configure resources for VM via custom profile
        if virt == "virtual-machine" and vm_resources is not None:
            self._create_vm_profile(name, vm_resources)
            instance_config["profiles"].append(name)

        return self._lxd.instances.create(config=instance_config, wait=True)

    def _create_vm_profile(self, name: str, vm_resources: VMResources) -> None:
        """Create custom profile for VM.

        Args:
            name: Name of the virtual machine profile.
            vm_resources: Configuration of the virtual machine resources.
        """
        try:
            vm_profile_config = {
                "limits.cpu": str(vm_resources.cpu),
                "limits.memory": vm_resources.memory,
            }
            vm_profile_devices = {
                "root": {
                    "path": "/",
                    "pool": "default",
                    "type": "disk",
                    "size": vm_resources.disk,
                }
            }
            self._lxd.profiles.create(
                name,
                vm_profile_config,
                vm_profile_devices,
            )
            logger.error(f"profile {vm_profile_config}")
        except AttributeError as error:
            raise RunnerError(
                "vm_resources variable was not defined in the correct format"
            ) from error
        except LXDAPIException as error:
            raise RunnerError(
                "VM resources were not provided in the correct format, check the juju"
                "config for vm-cpu, vm-memory and vm-disk."
            ) from error

    def _start_instance(self, instance: pylxd.models.Instance) -> None:
        """Start an instance and wait for it to boot.

        Args:
            instance: LXD instance of the runner.
        """
        instance.start(wait=True)

        # Wait for the instance to boot
        wait_interval = 15  # seconds
        attempts = int(self.reconcile_interval * 60 / wait_interval)
        for attempt in range(attempts):
            try:
                self._check_output(instance, ["who"])
                break
            except Exception:
                if attempt == attempts - 1:
                    raise RunnerStartError()
                else:
                    time.sleep(wait_interval)
