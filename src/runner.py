#!/usr/bin/env python3

import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from random import choices
from string import ascii_lowercase, digits

import requests
from jinja2 import Environment, FileSystemLoader

import fastcore.net
import pylxd
from ghapi.all import GhApi

logger = logging.getLogger(__name__)


class RunnerInfo:
    def __init__(self, name, local, remote):
        self.name = name
        self.local = local
        self.remote = remote

    @property
    def is_active(self):
        if not (self.local and self.remote):
            return False
        if self.local.status != "Running":
            return False
        if self.remote.status != "online":
            return False
        return True

    @property
    def is_offline(self):
        if not self.remote:
            return True
        if self.remote.status != "online":
            return True
        if not self.local or self.local.status != "Running":
            return True
        return False

    @property
    def is_unregistered(self):
        if self.remote and self.remote.status == "online":
            return False
        return self.local and self.local.status == "Running"

    @property
    def virt_type(self):
        if self.local:
            return self.local.type
        elif self.remote:
            remote_virt_type = (label["name"] for label in self.remote["labels"] if label["name"] in {"container", "virtual-machine"})
            return next(remote_virt_type, None)



class RunnerError(Exception):
    pass


class RunnerCreateFailed(RunnerError):
    pass


class RunnerRemoveFailed(RunnerError):
    pass


class RunnerManager:
    runner_bin_path = Path("/var/cache/github-runner-operator/runner.tgz")
    env_file = Path("/opt/github-runner/.env")

    def __init__(self, path, token, app_name):
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
        self.jinja = Environment(loader=FileSystemLoader("templates"))
        self.lxd = pylxd.Client()
        self.path = path
        self.api = GhApi(token=token)
        self.app_name = app_name

    @classmethod
    def install_deps(cls):
        """Install dependencies"""
        subprocess.run(["snap", "install", "lxd"], check=True)
        subprocess.run(["lxd", "init", "--auto"], check=True)
        cls.runner_bin_path.parent.mkdir(parents=True, exist_ok=True)

    def get_latest_runner_bin_url(self):
        """Get the URL for the latest runner binary."""
        # TODO: make these not hard-coded
        os_name = "linux"
        arch_name = "x64"

        if "/" in self.path:
            owner, repo = self.path.split("/")
            runner_bins = self.api.actions.list_runner_applications_for_repo(
                owner=owner, repo=repo
            )
        else:
            runner_bins = self.api.actions.list_runner_applications_for_org(
                org=self.path
            )
        for runner_bin in runner_bins:
            if runner_bin.os == os_name and runner_bin.architecture == arch_name:
                return runner_bin.download_url
        return None

    def update_runner_bin(self, download_url):
        """Download a runner file, replacing the current copy"""
        # Remove any existing runner bin file
        if self.runner_bin_path.exists():
            self.runner_bin_path.unlink()
        # Download the new file
        response = self.session.get(download_url)
        with self.runner_bin_path.open(mode="wb") as runner_bin_file:
            runner_bin_file.write(response.content)

    def get_info(self):
        """Return a list of RunnerInfo objects."""
        local_runners = {
            c.name: c
            for c in self.lxd.containers.all()
            if c.name.startswith(f"{self.app_name}-")
        }
        if "/" in self.path:
            owner, repo = self.path.split("/")
            remote_runners = self.api.actions.list_self_hosted_runners_for_repo(
                owner=owner, repo=repo
            )["runners"]
        else:
            remote_runners = self.api.actions.list_self_hosted_runners_for_org(
                org=self.path
            )["runners"]
        remote_runners = {
            r.name: r for r in remote_runners if r.name.startswith(f"{self.app_name}-")
        }
        runners = []
        for name in set(local_runners.keys()) | set(remote_runners.keys()):
            runners.append(
                RunnerInfo(name, local_runners.get(name), remote_runners.get(name))
            )
        return runners

    def reconcile(self, virt_type, quantity):
        """Bring runners in line with target."""
        active_runners = []
        stale_runners = []
        for runner in self.get_info():
            if runner.virt_type == virt_type:
                if runner.is_active:
                    active_runners.append(runner)
                else:
                    stale_runners.append(runner)

        if stale_runners:
            runner_names = ", ".join(r.name for r in stale_runners)
            logger.info(f"Cleaning up stale {virt_type} runners: {runner_names}")
            for runner in stale_runners:
                self._remove_runner(runner)

        delta = quantity - len(active_runners)
        if delta > 0:
            logger.info(f"Adding {delta} additional {virt_type} runners")
            for i in range(delta):
                self.create(image="ubuntu", virt=virt_type)
        elif delta < 0:
            active_runners.sort(key=lambda r: r.created_at)
            old_runners = active_runners[abs(delta) :]
            runner_names = ", ".join(r.name for r in old_runners)
            logger.info(f"Removing extra {virt_type} runners: {runner_names}")
            for runner in old_runners:
                self._remove_runner(runner)
        return delta

    def clear(self):
        """Clear out all existing runners."""
        runners = self.get_info()
        runner_names = ", ".join(r.name for r in runners)
        logger.info(f"Removing existing runners: {runner_names}")
        for runner in runners:
            self._remove_runner(runner)

    def create(self, image, virt="container"):
        """Create a runner"""
        instance = self._create_instance(image=image, virt=virt)
        instance.start(wait=True)
        try:
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
            self._load_aaprofile(instance)
        except Exception as e:
            instance.stop(wait=True)
            try:
                instance.delete(wait=True)
            except Exception:
                # Ephemeral containers should auto-delete when stopped;
                # this is just a fall-back.
                pass
            raise RunnerCreateFailed(str(e)) from e

    def _remove_runner(self, runner):
        """Remove a runner"""
        if runner.remote:
            try:
                if "/" in self.path:
                    owner, repo = self.path.split("/")
                    self.api.actions.delete_self_hosted_runner_from_repo(
                        owner=owner, repo=repo, runner_id=runner.remote.id
                    )
                else:
                    self.api.actions.delete_self_hosted_runner_from_org(
                        org=self.path, runner_id=runner.remote.id
                    )
            except Exception as e:
                raise RunnerRemoveFailed(
                    f"Failed remove remote runner: {runner.name}"
                ) from e

        if runner.local:
            try:
                if runner.local.status == "Running":
                    runner.local.stop(wait=True)
                    try:
                        runner.local.delete(wait=True)
                    except Exception:
                        # Ephemeral containers should auto-delete when stopped;
                        # this is just a fall-back.
                        pass
                else:
                    # We somehow have a non-running instance which should have been
                    # ephemeral. Try to delete it and allow any errors doing so to
                    # surface.
                    runner.local.delete(wait=True)
            except Exception as e:
                raise RunnerRemoveFailed(
                    f"Failed remove local runner: {runner.name}"
                ) from e

    def _register_runner(self, instance, labels):
        """Register a runner in an instance"""
        api = self.api
        if "/" in self.path:
            owner, repo = self.path.split("/")
            token = api.actions.create_registration_token_for_repo(
                owner=owner, repo=repo
            )
        else:
            token = api.actions.create_registration_token_for_org(org=self.path)
        cmd = (
            "sudo -u ubuntu /opt/github-runner/config.sh "
            f"--url https://github.com/{self.path} "
            "--token "
            f"{token.token} "
            "--ephemeral "
            "--name "
            f"{instance.name} "
            "--unattended "
            "--labels "
            f"{','.join(labels)}"
        )
        self._check_output(instance, cmd)

    def _start_runner(self, instance):
        """Start a runner that is already registered"""
        script_contents = self.jinja.get_template("start.j2").render()
        instance.files.put("/opt/github-runner/start.sh", script_contents)
        self._check_output(
            instance, "sudo chown ubuntu:ubuntu /opt/github-runner/start.sh"
        )
        self._check_output(instance, "sudo chmod u+x /opt/github-runner/start.sh")
        self._check_output(instance, "sudo -u ubuntu /opt/github-runner/start.sh")

    def _load_aaprofile(self, instance):
        """Load the apparmor profile so classic snaps can run"""
        self._check_output(
            instance,
            ["bash", "-c", "sudo apparmor_parser -r /etc/apparmor.d/*snap-confine*"],
            False,
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

    def _configure_runner(self, instance):
        """Configure the runner"""
        # Render proxies if configured
        if self.proxies:
            contents = self.jinja.get_template("env.j2").render(proxies=self.proxies)
            instance.files.put(self.env_file, contents)
            self._check_output(instance, "chown ubuntu:ubuntu /opt/github-runner/.env")

    def _install_binary(self, instance):
        """Install the binary in a instance"""
        instance.files.mk_dir("/opt/github-runner")
        for attempt in range(10):
            try:
                instance.files.put("/tmp/runner.tgz", self.runner_bin_path.read_bytes())
                self._check_output(
                    instance, "tar -xzf /tmp/runner.tgz -C /opt/github-runner"
                )
                self._check_output(
                    instance, "chown -R ubuntu:ubuntu /opt/github-runner"
                )
                break
            except subprocess.CalledProcessError:
                if attempt < 9:
                    logger.warning("Failed to install runner, trying again")
                    time.sleep(0.5)
                else:
                    logger.error("Failed to install runner, giving up")
                    raise

    def _check_output(self, container, cmd, split=True):
        """Check execution of a command in a container"""
        if split:
            cmd = cmd.split()
        exit_code, stdout, stderr = container.execute(cmd)
        logger.debug(f"Exit code {exit_code} from {cmd}")
        subprocess.CompletedProcess(cmd, exit_code, stdout, stderr).check_returncode()
        return stdout

    def _create_instance(self, image="focal", virt="container"):
        """Create an instance"""
        suffix = "".join(choices(ascii_lowercase + digits, k=6))
        if not self.lxd.profiles.exists("runner"):
            config = {
                "security.nesting": "true",
                "security.privileged": "true",
                # "raw.lxc": "lxc.apparmor.profile=unconfined",
            }
            devices = {}
            self.lxd.profiles.create("runner", config, devices)
        config = {
            "name": f"{self.app_name}-{suffix}",
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
        return self.lxd.instances.create(config=config, wait=True)
