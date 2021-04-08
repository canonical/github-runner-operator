#!/usr/bin/env python3

import io
import os
import tarfile
from pathlib import Path

import requests


class Runner:
    release_url = "https://api.github.com/repos/actions/runner/releases/latest"
    runner_path = Path("/opt/github-runner")

    def __init__(self):
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY", None)
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY", None)
        proxies = {}
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy
        self.session = requests.Session()
        if proxies:
            self.session.proxies.update(proxies)

    def download(self):
        """Download and extract the latest release"""
        # response = requests.get(self.release_url, allow_redirects=True, proxies=self.proxies)
        response = self.session.get(self.release_url, allow_redirects=True)
        content = response.json()
        download_url = None
        for asset in content["assets"]:
            if asset["name"].startswith("actions-runner-linux-x64"):
                download_url = asset["browser_download_url"]
        response = self.session.get(download_url)
        with tarfile.open(
            mode="r:gz", fileobj=io.BytesIO(response.content)
        ) as tar_file:
            tar_file.extractall(path=self.runner_path)
