# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Runner Manager manages the runners on LXD and GitHub."""

from __future__ import annotations

import hashlib
import logging
import tarfile
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import fastcore.net
import jinja2
import pylxd
import pylxd.models
import requests
import requests.adapters
import urllib3
from ghapi.all import GhApi

from errors import RunnerBinaryError, RunnerCreateError
from github_type import (
    GitHubRunnerStatus,
    RegisterToken,
    RunnerApplication,
    RunnerApplicationList,
    SelfHostedRunner,
)
from runner import Runner, RunnerConfig
from runner_type import GitHubOrg, GitHubPath, GitHubRepo, ProxySetting, VirtualMachineResources
from utilities import get_env_var, retry

logger = logging.getLogger(__name__)


@dataclass
class RunnerInfo:
    """Information from GitHub of a runner.

    Used as a returned type to method querying runner information.

    TODO:
        See if more information should be shared by the charm.
    """

    name: str
    status: GitHubRunnerStatus


class RunnerManager:
    """Manage a group of runners according to configuration."""

    def __init__(
        self,
        path: GitHubPath,
        token: str,
        app_name: str,
        reconcile_interval: int,
        image: str = "focal",
    ) -> None:
        """Construct RunnerManager object for creating and managing runners.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            token: GitHub personal access token to register runner to the repository or
                organization.
            app_name: An name for the set of runners.
            reconcile_interval: Number of minutes between each reconciliation of runners.
            image: Image to use for the runner LXD instances.
        """
        http_proxy = get_env_var("JUJU_CHARM_HTTP_PROXY")
        https_proxy = get_env_var("JUJU_CHARM_HTTPS_PROXY")
        no_proxy = get_env_var("JUJU_CHARM_NO_PROXY")

        self.proxies: ProxySetting = {}
        if http_proxy:
            self.proxies["http"] = http_proxy
        if https_proxy:
            self.proxies["https"] = https_proxy
        if no_proxy:
            self.proxies["no_proxy"] = no_proxy

        self.session = requests.Session()
        # TODO: Review the retry strategy
        adapter = requests.adapters.HTTPAdapter(
            max_retries=urllib3.Retry(
                total=10, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504]
            )
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        if self.proxies:
            # setup proxy for requests
            self.session.proxies.update(self.proxies)
            # add proxy to fastcore which ghapi uses
            proxy = urllib.request.ProxyHandler(self.proxies)
            opener = urllib.request.build_opener(proxy)
            fastcore.net._opener = opener

        self._github = GhApi(token=token)
        self._jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True
        )
        self._lxd = pylxd.Client()

        self.path = path

        self.app_name = app_name
        self.reconcile_interval = reconcile_interval
        self.image = image

        self.runner_bin_path: Optional[GitHubPath] = None

    @retry(tries=5, delay=30, logger=logger)
    def get_latest_runner_bin_url(
        self, os_name: str = "linux", arch_name: str = "x64"
    ) -> RunnerApplication:
        """Get the URL for the latest runner binary.

        The runner binary URL changes when a new version is available.

        Args:
            os_name: Name of operating system.
            arch_name: Name of architecture.

        Returns:
            Information on the runner application.
        """
        runner_bins: RunnerApplicationList = []
        if isinstance(self.path, GitHubRepo):
            runner_bins = self._github.actions.list_runner_applications_for_repo(
                owner=self.path.owner, repo=self.path.repo
            )
        if isinstance(self.path, GitHubOrg):
            runner_bins = self._github.actions.list_runner_application_for_org(org=self.path.org)

        logger.debug("Response of runner binary list: %s", runner_bins)

        try:
            return next(
                bin for bin in runner_bins if bin.os == os_name and bin.architecture == arch_name
            )
        except StopIteration as err:
            raise RunnerBinaryError(
                f"Unable query GitHub runner binary information for {os_name} {arch_name}"
            ) from err

    @retry(tries=5, delay=30, logger=logger)
    def update_runner_bin(self, binary: RunnerApplication) -> None:
        """Download a runner file, replacing the current copy.

        Remove the existing runner binary to prevent it from being used. This
        is done to prevent security issues arising from outdated runner binary
        containing security flaws. The newest version of runner binary should
        always be used.

        Args:
            binary: Information on the runner binary to download.

        TODO:
            Convert to download of runner binary to streaming to file, rather than save in memory
            then copy to file. Ignore if the file size is too small.
        """
        logger.info("Downloading runner binary from: %s", binary.download_url)

        # Delete old version of runner binary.
        if self.runner_bin_path is not None:
            self.runner_bin_path.unlink(missing_ok=True)
            self.runner_bin_path = None

        # Download the new file
        response = self.session.get(binary.download_url, stream=True)

        logger.info(
            "Download of runner binary from %s return status code: %i",
            binary.download_url,
            response.status_code,
        )

        if binary.sha256_checksum:
            hash = hashlib.sha256()

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            for chunk in response.iter_content(chunk_size=4096, decode_unicode=False):
                tmp_file.write(chunk)

                if binary.sha256_checksum:
                    hash.update(chunk)

        logger.info("Finished download of runner binary.")

        # Verify the checksum if checksum is present.
        if binary.sha256_checksum:
            if binary.sha256_checksum != hash.hexdigest():
                logger.error(
                    "Mismatch of excepted hash of runner binary (%s) and calculated hash (%s)",
                    binary.sha256_checksum,
                    hash,
                )
                raise RunnerBinaryError("Checksum mismatch for downloaded runner binary")
        else:
            logger.warning("Checksum for runner binary is not found, download not verified.")

        # Verify the file integrity.
        if not tarfile.is_tarfile(tmp_file.name):
            logger.error("Failed to decompress downloaded GitHub runner binary.")
            raise RunnerBinaryError("Downloaded runner binary cannot be decompressed.")

        # Make the binary accessible after verification has passed.
        self.runner_bin_path = Path(tmp_file.name)

        logger.info("Validated newly downloaded runner binary and enabled it.")

    def get_github_info(self) -> list[RunnerInfo]:
        """Get information on the runners from GitHub.

        Returns:
            List of information from GitHub on runners.
        """
        remote_runners = self._get_runner_github_info()
        return [RunnerInfo(r.name, r.status) for r in remote_runners.values()]

    def reconcile(self, quantity: int, resources: VirtualMachineResources) -> int:
        """Bring runners in line with target.

        Args:
            quantity: Number of intended runners.
            resources: Configuration of the virtual machine resources.

        Returns:
            Difference between intended runners and actual runners.
        """
        runners = self._get_runners()

        # Clean up offline runners
        offline_runners = [r for r in runners if not r.online]
        if offline_runners:
            logger.info("Cleaning up offline runners.")

            for runner in offline_runners:
                runner.remove()
                logger.info("Removed runner: %s", runner.name)

        # Add/Remove runners to match the target quantity
        online_runners = [r for r in runners if r.exist and r.online]
        delta = quantity - len(online_runners)
        if delta > 0:
            if self.runner_bin_path is None:
                raise RunnerCreateError("Unable to create runner due to missing runner binary.")

            logger.info("Getting registration token for GitHub runners.")

            token: RegisterToken = {"token": None}
            if isinstance(self.path, GitHubRepo):
                token = self._github.actions.create_registration_token_for_repo(
                    owner=self.path.owner, repo=self.path.repo
                )
            elif isinstance(self.path, GitHubOrg):
                token = self._github.actions.create_registration_token_for_org(org=self.path.org)

            logger.info("Adding %i additional runner(s).", delta)
            for _ in range(delta):
                config = RunnerConfig(
                    self.app_name, self.path, self.proxies, self._generate_runner_name()
                )
                runner = Runner(self._github, self._jinja, self._lxd, config)
                runner.create(
                    self.image,
                    resources,
                    self.runner_bin_path,
                    token.token,
                )
                logger.info("Created runner: %s", runner.name)
        elif delta < 0:
            # Idle runners are online runners that has not taken a job.
            idle_runners = [runner for runner in online_runners if not runner.busy]
            offset = min(-delta, len(idle_runners))
            if offset != 0:
                logger.info("Removing %i runner(s).", offset)
                remove_runners = idle_runners[:offset]

                logger.info("Cleaning up idle runners.")

                for runner in remove_runners:
                    runner.remove()
                    logger.info("Removed runner: %s", runner.name)

            else:
                logger.info("There are no idle runner to remove.")
        else:
            logger.info("No changes to number of runner needed.")

        return delta

    def flush(self, flush_busy: bool = True) -> int:
        """Remove existing runners.

        Args:
            flush_busy: Whether to flush busy runners as well.

        Returns:
            Number of runner removed.
        """
        if flush_busy:
            runners = [runner for runner in self._get_runners() if runner.exist]
        else:
            runners = [
                runner for runner in self._get_runners() if runner.exist and not runner.busy
            ]
        runner_names = ", ".join(runner.name for runner in runners)
        logger.info("Removing existing local runners: %s", runner_names)

        for runner in runners:
            runner.remove()

        return len(runners)

    def _generate_runner_name(self) -> str:
        """Generate a runner name based on charm name.

        Returns:
            Generated name of runner.
        """
        suffix = str(uuid.uuid4())
        return f"{self.app_name}-{suffix}"

    def _get_runner_github_info(self) -> Dict[str, SelfHostedRunner]:
        remote_runners_list: list[SelfHostedRunner] = []
        if isinstance(self.path, GitHubRepo):
            remote_runners_list = self._github.actions.list_self_hosted_runners_for_repo(
                owner=self.path.owner, repo=self.path.repo
            )["runners"]
        if isinstance(self.path, GitHubOrg):
            remote_runners_list = self._github.actions.list_self_hosted_runners_for_org(
                org=self.path.org
            )["runners"]

        return {
            runner.name: runner
            for runner in remote_runners_list
            if runner.name.startswith(f"{self.app_name}-")
        }

    def _get_runners(self) -> list[Runner]:
        """Query for the list of runners.

        Returns:
            List of `Runner` from information on LXD or GitHub.
        """

        def create_runner(
            name: str,
            local_runner: Optional[pylxd.models.Instance],
            remote_runner: Optional[SelfHostedRunner],
        ) -> Runner:
            """Create runner from information from GitHub and LXD."""
            running = local_runner is not None
            online = False if remote_runner is None else remote_runner["status"] == "online"
            busy = False if remote_runner is None else remote_runner["busy"]

            config = RunnerConfig(self.app_name, self.path, self.proxies, name)
            return Runner(
                self._github,
                self._jinja,
                self._lxd,
                config,
                running,
                online,
                busy,
                local_runner,
            )

        remote_runners = self._get_runner_github_info()
        local_runners = {
            instance.name: instance
            for instance in self._lxd.instances.all()
            if instance.name.startswith(f"{self.app_name}-")
        }

        runners: list[Runner] = []
        for name in set(local_runners.keys()) | set(remote_runners.keys()):
            runners.append(create_runner(name, local_runners.get(name), remote_runners.get(name)))

        return runners
