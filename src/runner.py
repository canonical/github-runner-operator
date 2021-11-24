#!/usr/bin/env python3

import logging
import os
import subprocess
import time
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


class Runner:
    release_url = "https://api.github.com/repos/actions/runner/releases/latest"
    runner_path = Path("/opt/github-runner")
    env_file = runner_path / ".env"

    def __init__(self, path, token):
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

    def install(self):
        """Install dependencies"""
        cmd = "sudo snap install lxd"
        subprocess.check_output(cmd.split())
        cmd = "sudo lxd init --auto"
        subprocess.check_output(cmd.split())

    def create(self, image, virt="container", wait=False):
        """Create a runner"""
        instance = self._create_instance(image=image, virt=virt)
        instance.start(wait=True)
        try:
            self._install_binary(instance)
            self._configure_runner(instance)
            self._register_runner(
                instance,
                labels=[
                    image,
                ],
            )
            self._start_runner(instance)
            self._load_aaprofile(instance)
        except RuntimeError as e:
            instance.stop(wait=True)
            raise e

    def active_count(self):
        """Return the number of active runners"""
        count = 0
        for container in self.lxd.containers.all():
            if container.name.startswith("runner-"):
                count += 1
        return count

    def remove_runners(self):
        """Remove runners"""
        api = self.api
        repo = None
        if "/" in self.path:
            owner, repo = self.path.split("/")
        hosted_runners = [container.name for container in self.lxd.containers.all()]
        for runner in self._get_runners()["runners"]:
            if runner.name in hosted_runners:
                logger.info(f"Deregistering runner {runner.name}")
                if repo:
                    api.actions.delete_self_hosted_runner_from_repo(
                        owner=owner, repo=repo, runner_id=runner.id
                    )
                else:
                    api.actions.delete_self_hosted_runner_from_org(
                        org=self.path, runner_id=runner.id
                    )

    def _get_runners(self):
        """Return the runner data"""
        api = self.api
        repo = False
        if "/" in self.path:
            owner, repo = self.path.split("/")
        if repo:
            runners = api.actions.list_self_hosted_runners_for_repo(
                owner=owner, repo=repo
            )
        else:
            runners = api.actions.list_self_hosted_runners_for_org(org=self.path)
        return runners

    def _register_runner(self, container, labels):
        """Register a runner in a container"""
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
            f"{container.name} "
            "--unattended "
            "--labels "
            f"{','.join(labels)}"
        )
        self._check_output(container, cmd)

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
        binary = self._get_runner_binary()
        instance.files.mk_dir("/opt/github-runner")
        while True:
            try:
                instance.files.put("/tmp/runner.tgz", binary.read_bytes())
                self._check_output(
                    instance, "tar -xzf /tmp/runner.tgz -C /opt/github-runner"
                )
                self._check_output(
                    instance, "chown -R ubuntu:ubuntu /opt/github-runner"
                )
                break
            except subprocess.CalledProcessError:
                logger.warning("Failed to install runner, trying again")
                time.sleep(0.5)

    def _check_output(self, container, cmd, split=True):
        """Check execution of a command in a container"""
        if split:
            cmd = cmd.split()
        exit_code, stdout, stderr = container.execute(cmd)
        logger.debug(f"Exit code {exit_code} from {cmd}")
        subprocess.CompletedProcess(cmd, exit_code, stdout, stderr).check_returncode()
        return stdout

    def _get_runner_binary(self):
        """Download a runner file"""
        # Find the file name
        response = self.session.get(self.release_url, allow_redirects=True)
        content = response.json()
        if not content:
            raise RuntimeError("Unable to find github release")
        download_url = None
        for asset in content["assets"]:
            if "linux-x64" in asset["name"]:
                download_url = asset["browser_download_url"]
                file_name = asset["name"]
        # Return if existing
        runner_binary = Path(f"/tmp/{file_name}")
        if runner_binary.exists():
            return runner_binary
        # Remove any old versions before downloading
        for path in Path("/tmp/").glob("*linux-x64*"):
            path.unlink()
        response = self.session.get(download_url)
        with runner_binary.open(mode="wb") as tmp_file:
            tmp_file.write(response.content)
        return runner_binary

    def _create_instance(self, image="focal", virt="container"):
        """Create an instance"""
        suffix = "".join(choices(ascii_lowercase + digits, k=6))
        if not self.lxd.profiles.exists("runner"):
            config = {
                "security.nesting": "true",
                "security.privileged": "true",
                "raw.lxc": "lxc.apparmor.profile=unconfined",
            }
            devices = {}
            self.lxd.profiles.create("runner", config, devices)
        config = {
            "name": f"runner-{suffix}",
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
