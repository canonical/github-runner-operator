import logging
import os
import random
import string
import subprocess
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import fastcore.net
import jinja2
import pylxd
import pylxd.models
import requests
import requests.adapters
import urllib3
from ghapi.all import GhApi

from errors import RunnerBinaryError
from github_type import RunnerApplicationList, SelfHostedRunner
from retry import retry
from runner import Runner
from runner_type import GitHubOrg, GitHubRepo, ProxySetting, VirtualMachineResources

logger = logging.getLogger(__name__)


@dataclass
class RunnerInfo:
    """Information from GitHub of a runner.

    Used as a returned type to method querying runner information.

    TODO:
        See if more information should be shared by the charm.
    """

    name: str
    online: bool
    offline: bool


class RunnerManager:

    # TODO: Verify if this violates bandit B108.
    runner_bin_path = Path("/var/cache/github-runner-operator/runner.tgz")

    def __init__(
        self, path: str, token: str, app_name: str, reconcile_interval: int, image: str = "focal"
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

        TODO:
            Move `install_deps` class method elsewhere.

            Change the `path` in `__init__` method to type `GitHubPath`.
        """
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY", None)
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY", None)
        no_proxy = os.environ.get("JUJU_CHARM_NO_PROXY", None)

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

        if "/" in path:
            owner, repo = path.split("/")
            self.path = GitHubRepo(owner=owner, repo=repo)
        else:
            self.path = GitHubOrg(org=path)

        self.app_name = app_name
        self.reconcile_interval = reconcile_interval
        self.image = image

    @classmethod
    @retry(tries=10, delay=15, max_delay=60, backoff=1.5)
    def install_deps(cls) -> None:
        """Install dependencies."""

        def execute(cmd: Sequence[str], check: bool = True) -> str:
            """Execute a command on a subprocess.

            Args:
                cmd: Command in a list.
                check: Whether to throw error on non-zero exit code. Defaults to True.

            Returns:
                Output on stdout.

            TODO:
                Move this function elsewhere and share this with event_timer.py.
            """

            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            logger.debug("Command %s returns: %s", " ".join(cmd), result.stdout)

            if check:
                try:
                    result.check_returncode()
                except subprocess.CalledProcessError as err:
                    logger.error(
                        "Command %s failed with code %i: %s",
                        " ".join(cmd),
                        err.returncode,
                        err.stderr,
                    )
                    raise

        logger.info("Installing charm dependencies.")
        # Binding for snap, apt, and lxd init commands are not available so subprocess.run used.
        execute(["/usr/bin/apt", "remove", "-qy", "lxd", "lxd-client"], check=False)
        execute(["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"])
        execute(["/usr/bin/snap", "refresh", "lxd", "--channel=latest/stable"])
        execute(["/snap/bin/lxd", "waitready"])
        execute(["/snap/bin/lxd", "init", "--auto"])
        execute(["/usr/bin/chmod", "a+wr", "/var/snap/lxd/common/lxd/unix.socket"])
        execute(["/snap/bin/lxc", "network", "set", "lxdbr0", "ipv6.address", "none"])
        execute(
            [
                "/usr/bin/apt",
                "install",
                "-qy",
                "cpu-checker",
                "libvirt-clients",
                "libvirt-daemon-driver-qemu",
            ],
        )
        cls.runner_bin_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Finished installing charm dependencies.")

    def get_latest_runner_bin_url(self, os_name: str = "linux", arch_name: str = "x64") -> str:
        """Get the URL for the latest runner binary.

        The runner binary URL changes when a new version is available.

        Returns:
            The URL to the latest runner binary.
        """

        runner_bins: RunnerApplicationList = []
        if isinstance(self.path, GitHubRepo):
            runner_bins = self._github.actions.list_runner_applications_for_repo(
                owner=self.path.owner, repo=self.path.repo
            )
        elif isinstance(self.path, GitHubOrg):
            runner_bins = self._github.actions.list_runner_application_for_org(org=self.path.org)

        logger.debug("Response of runner binary list: %s", runner_bins)

        for bin in runner_bins:
            if bin.os == os_name and bin.architecture == arch_name:
                return bin.download_url

        raise RunnerBinaryError(
            f"Unable to download GitHub runner binary for {os_name} {arch_name}"
        )

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5)
    def update_runner_bin(self, download_url: str) -> None:
        """Download a runner file, replacing the current copy.

        Args:
            download_url (str): URL to download the runner binary.

        TODO:
            Deletion first cause no runner binary on download failure. See if this cause problems.
        """
        logger.info("Downloading runner binary from: %s", download_url)

        # Remove any existing runner bin file
        if self.runner_bin_path.exists():
            self.runner_bin_path.unlink()
        # Download the new file
        response = self.session.get(download_url)

        logger.info("Download of runner binary return status code: %i", response.status_code)

        with self.runner_bin_path.open(mode="wb") as runner_bin_file:
            runner_bin_file.write(response.content)

        # Verify the file integrity.
        with tarfile.open(self.runner_bin_path, "r:gz") as f:
            try:
                logger.debug(
                    "Downloaded GitHub runner binary contains files: %s", ", ".join(f.getnames())
                )
            except tarfile.TarError:
                logger.error("Failed to decompress downloaded GitHub runner binary.")
                raise

    def get_github_info(self) -> List[RunnerInfo]:
        """Get information on the runners from GitHub.

        Returns:
            List of information from GitHub on runners.
        """
        remote_runners = self._get_runner_github_info()
        return [
            RunnerInfo(r.name, r.status == "online", r.status == "offline")
            for r in remote_runners.values()
        ]

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
            runner_names = ", ".join(r.name for r in offline_runners)
            logger.info("Cleaning up offline runners: %s", runner_names)

            for runner in offline_runners:
                runner.remove()

        # Add/Remove runners to match the target quantity
        online_runners = [r for r in runners if r.exist and r.online]
        delta = quantity - len(online_runners)
        if delta > 0:
            logger.info("Getting registration token for GitHub runners.")
            if isinstance(self.path, GitHubRepo):
                token = self._github.actions.create_registration_token_for_repo(
                    owner=self.path.owner, repo=self.path.repo
                )
            else:
                token = self._github.actions.create_registration_token_for_org(org=self.path.org)

            logger.info("Adding %i additional runner(s)", delta)
            for _ in range(delta):
                runner = Runner(
                    self._github,
                    self._jinja,
                    self._lxd,
                    self.app_name,
                    self.path,
                    self.proxies,
                    self._generate_runner_name(),
                )
                runner.create(
                    self.image, resources, self.runner_bin_path, self.reconcile_interval, token
                )
        elif delta < 0:
            idle_runners = [r for r in online_runners if not r.busy]
            offset = min(-delta, len(idle_runners))
            if offset != 0:
                logger.info("Removing %i runner(s)", offset)
                remove_runners = idle_runners[:offset]
                runner_names = ", ".join(r.name for r in remove_runners)
                for runner in remove_runners:
                    runner.remove()
            else:
                logger.info("There are no idle runner to remove.")

        return delta

    def clean(self) -> int:
        """Remove existing runners.

        Returns:
            Number of runner removed.
        """

        runners = [r for r in self._get_runners() if r.exist]
        runner_names = ", ".join(r.name for r in runners)
        logger.info("Removing existing local runners: %s", runner_names)

        for runner in runners:
            runner.remove()

        return len(runners)

    def _generate_runner_name(self) -> str:
        """Generate a runner name based on charm name.

        Returns:
            Generated name of runner.

        TODO:
            Consider name collusion. LXD would fail to create VM on name collusion.
        """
        # Generated a suffix for naming propose, not used as secret.
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))  # nosec B311
        return f"{self.app_name}-{suffix}"

    def _get_runner_github_info(self) -> Dict[str, SelfHostedRunner]:
        remote_runners_list: List[SelfHostedRunner] = []
        if isinstance(self.path, GitHubRepo):
            remote_runners_list = self._github.actions.list_self_hosted_runners_for_repo(
                owner=self.path.owner, repo=self.path.repo
            )["runners"]
        elif isinstance(self.path, GitHubOrg):
            remote_runners_list = self._github.actions.list_self_hosted_runners_for_org(
                org=self.path.org
            )["runners"]

        return {r.name: r for r in remote_runners_list if r.name.startswith(f"{self.app_name}-")}

    def _get_runners(self) -> List[Runner]:
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

            return Runner(
                self._github,
                self._jinja,
                self._lxd,
                self.app_name,
                self.path,
                self.proxies,
                name,
                running,
                online,
                busy,
                local_runner,
            )

        remote_runners = self._get_runner_github_info()
        local_runners = {
            i.name: i for i in self._lxd.instances.all() if i.name.startswith(f"{self.app_name}-")
        }

        runners: List[Runner] = []
        for name in set(local_runners.keys()) | set(remote_runners.keys()):
            runners.append(create_runner(name, local_runners.get(name), remote_runners.get(name)))

        return runners
