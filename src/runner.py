#!/usr/bin/env python3

import io
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import requests

from jinja2 import Environment, FileSystemLoader


class Runner:
    release_url = "https://api.github.com/repos/actions/runner/releases/latest"
    runner_path = Path("/opt/github-runner")
    env_file = runner_path / ".env"

    def __init__(self):
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
            self.session.proxies.update(self.proxies)
        self.jinja = Environment(loader=FileSystemLoader("templates"))

    def download(self):
        """Download and extract the latest release"""
        # Find the file name
        response = self.session.get(self.release_url, allow_redirects=True)
        content = response.json()
        download_url = None
        for asset in content["assets"]:
            if asset["name"].startswith("actions-runner-linux-x64"):
                download_url = asset["browser_download_url"]
        # Download and untar
        response = self.session.get(download_url)
        with tarfile.open(
            mode="r:gz", fileobj=io.BytesIO(response.content)
        ) as tar_file:
            tar_file.extractall(path=self.runner_path)
        # Make the directory accessable to ubuntu
        for directory, _, files in os.walk(self.runner_path):
            shutil.chown(directory, user="ubuntu", group="ubuntu")
            for file in files:
                shutil.chown(
                    os.path.join(directory, file), user="ubuntu", group="ubuntu"
                )

    def setup_env(self):
        """Setup the environment file"""
        # Render proxies if configured
        if self.proxies:
            with self.env_file.open(mode="w") as env_file:
                contents = self.jinja.get_template("env.j2").render(
                    proxies=self.proxies
                )
                env_file.write(contents)
            shutil.chown(self.env_file, user="ubuntu", group="ubuntu")

    def register(self, url, token):
        """Register the runner with the provided token"""
        cmd = f"sudo -u ubuntu ./config.sh --url {url} --token {token} --unattended"
        subprocess.check_output(cmd, cwd=self.runner_path, shell=True)
