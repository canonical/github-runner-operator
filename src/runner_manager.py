# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Runner Manager manages the runners on LXD and GitHub."""

import hashlib
import logging
import random
import secrets
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterator, Optional, Type

import jinja2
import requests
import requests.adapters
import urllib3

import errors
import github_metrics
import metrics
import runner_logs
import runner_metrics
import shared_fs
from charm_state import VirtualMachineResources
from errors import IssueMetricEventError, RunnerBinaryError, RunnerCreateError
from github_client import GithubClient
from github_type import RunnerApplication, SelfHostedRunner
from lxd import LxdClient, LxdInstance
from repo_policy_compliance_client import RepoPolicyComplianceClient
from runner import LXD_PROFILE_YAML, CreateRunnerConfig, Runner, RunnerConfig, RunnerStatus
from runner_manager_type import FlushMode, RunnerInfo, RunnerManagerClients, RunnerManagerConfig
from runner_metrics import RUNNER_INSTALLED_TS_FILE_NAME
from runner_type import ProxySetting as RunnerProxySetting
from runner_type import RunnerByHealth
from utilities import execute_command, retry, set_env_var

REMOVED_RUNNER_LOG_STR = "Removed runner: %s"

logger = logging.getLogger(__name__)


BUILD_IMAGE_SCRIPT_FILENAME = Path("scripts/build-lxd-image.sh")

IssuedMetricEventsStats = dict[Type[metrics.Event], int]


class RunnerManager:
    """Manage a group of runners according to configuration."""

    runner_bin_path = Path("/home/ubuntu/github-runner-app")
    cron_path = Path("/etc/cron.d")

    def __init__(
        self,
        app_name: str,
        unit: int,
        runner_manager_config: RunnerManagerConfig,
    ) -> None:
        """Construct RunnerManager object for creating and managing runners.

        Args:
            app_name: An name for the set of runners.
            unit: Unit number of the set of runners.
            runner_manager_config: Configuration for the runner manager.
        """
        self.app_name = app_name
        self.instance_name = f"{app_name}-{unit}"
        self.config = runner_manager_config
        self.proxies = runner_manager_config.charm_state.proxy_config

        # Setting the env var to this process and any child process spawned.
        if no_proxy := self.proxies.no_proxy:
            set_env_var("NO_PROXY", no_proxy)
        if http_proxy := self.proxies.http:
            set_env_var("HTTP_PROXY", http_proxy)
        if https_proxy := self.proxies.https:
            set_env_var("HTTPS_PROXY", https_proxy)

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=urllib3.Retry(
                total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504]
            )
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # The repo policy compliance service is on localhost and should not have any proxies
        # setting configured. The is a separated requests Session as the other one configured
        # according proxies setting provided by user.
        local_session = requests.Session()
        local_session.mount("http://", adapter)
        local_session.mount("https://", adapter)
        local_session.trust_env = False

        self._clients = RunnerManagerClients(
            GithubClient(token=self.config.token),
            jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True),
            LxdClient(),
            RepoPolicyComplianceClient(
                local_session, "http://127.0.0.1:8080", self.config.service_token
            ),
        )

    def check_runner_bin(self) -> bool:
        """Check if runner binary exists.

        Returns:
            Whether runner bin exists.
        """
        return self.runner_bin_path.exists()

    @retry(tries=5, delay=30, local_logger=logger)
    def get_latest_runner_bin_url(self, os_name: str = "linux") -> RunnerApplication:
        """Get the URL for the latest runner binary.

        The runner binary URL changes when a new version is available.

        Args:
            os_name: Name of operating system.

        Raises:
            RunnerBinaryError: If an error occurred while fetching runner application info.

        Returns:
            Information on the runner application.
        """
        try:
            return self._clients.github.get_runner_application(
                path=self.config.path, arch=self.config.charm_state.arch.value, os=os_name
            )
        except RunnerBinaryError:
            logger.error("Failed to get runner application info.")
            raise

    @retry(tries=5, delay=30, local_logger=logger)
    def update_runner_bin(self, binary: RunnerApplication) -> None:
        """Download a runner file, replacing the current copy.

        Remove the existing runner binary to prevent it from being used. This
        is done to prevent security issues arising from outdated runner
        binaries containing security flaws. The newest version of runner binary
        should always be used.

        Args:
            binary: Information on the runner binary to download.
        """
        logger.info("Downloading runner binary from: %s", binary["download_url"])

        try:
            # Delete old version of runner binary.
            RunnerManager.runner_bin_path.unlink(missing_ok=True)
        except OSError as err:
            logger.exception("Unable to perform file operation on the runner binary path")
            raise RunnerBinaryError("File operation failed on the runner binary path") from err

        try:
            # Download the new file
            response = self.session.get(binary["download_url"], stream=True)

            logger.info(
                "Download of runner binary from %s return status code: %i",
                binary["download_url"],
                response.status_code,
            )

            if not binary["sha256_checksum"]:
                logger.error("Checksum for runner binary is not found, unable to verify download.")
                raise RunnerBinaryError(
                    "Checksum for runner binary is not found in GitHub response."
                )

            sha256 = hashlib.sha256()

            with RunnerManager.runner_bin_path.open(mode="wb") as file:
                # Process with chunk_size of 128 KiB.
                for chunk in response.iter_content(chunk_size=128 * 1024, decode_unicode=False):
                    file.write(chunk)

                    sha256.update(chunk)
        except requests.RequestException as err:
            logger.exception("Failed to download of runner binary")
            raise RunnerBinaryError("Failed to download runner binary") from err

        logger.info("Finished download of runner binary.")

        # Verify the checksum if checksum is present.
        if binary["sha256_checksum"] != sha256.hexdigest():
            logger.error(
                "Expected hash of runner binary (%s) doesn't match the calculated hash (%s)",
                binary["sha256_checksum"],
                sha256,
            )
            raise RunnerBinaryError("Checksum mismatch for downloaded runner binary")

        # Verify the file integrity.
        if not tarfile.is_tarfile(file.name):
            logger.error("Failed to decompress downloaded GitHub runner binary.")
            raise RunnerBinaryError("Downloaded runner binary cannot be decompressed.")

        logger.info("Validated newly downloaded runner binary and enabled it.")

    def get_github_info(self) -> Iterator[RunnerInfo]:
        """Get information on the runners from GitHub.

        Returns:
            List of information from GitHub on runners.
        """
        remote_runners = self._get_runner_github_info()
        return (
            RunnerInfo(runner.name, runner.status, runner.busy)
            for runner in remote_runners.values()
        )

    def _get_runner_health_states(self) -> RunnerByHealth:
        local_runners = [
            instance
            # Pylint cannot find the `all` method.
            for instance in self._clients.lxd.instances.all()  # pylint: disable=no-member
            if instance.name.startswith(f"{self.instance_name}-")
        ]

        healthy = []
        unhealthy = []

        for runner in local_runners:
            _, stdout, _ = runner.execute(["ps", "aux"])
            if f"/bin/bash {Runner.runner_script}" in stdout.read().decode("utf-8"):
                healthy.append(runner.name)
            else:
                unhealthy.append(runner.name)

        return RunnerByHealth(healthy, unhealthy)

    def _create_runner(
        self, registration_token: str, resources: VirtualMachineResources, runner: Runner
    ):
        """Create a runner.

        Issues RunnerInstalled metric if metrics_logging is enabled.

        Args:
            registration_token: Token for registering runner to GitHub.
            resources: Configuration of the virtual machine resources.
            runner: Runner to be created.
        """
        if self.config.are_metrics_enabled:
            ts_now = time.time()
            runner.create(
                config=CreateRunnerConfig(
                    image=self.config.image,
                    resources=resources,
                    binary_path=RunnerManager.runner_bin_path,
                    registration_token=registration_token,
                    arch=self.config.charm_state.arch,
                )
            )
            ts_after = time.time()
            try:
                metrics.issue_event(
                    event=metrics.RunnerInstalled(
                        timestamp=ts_after,
                        flavor=self.app_name,
                        duration=ts_after - ts_now,
                    ),
                )
            except IssueMetricEventError:
                logger.exception("Failed to issue RunnerInstalled metric")

            try:
                fs = shared_fs.get(runner.config.name)
            except errors.GetSharedFilesystemError:
                logger.exception(
                    "Failed to get shared filesystem for runner %s, "
                    "will not be able to issue all metrics.",
                    runner.config.name,
                )
            else:
                try:
                    (fs.path / RUNNER_INSTALLED_TS_FILE_NAME).write_text(
                        str(ts_after), encoding="utf-8"
                    )
                except FileNotFoundError:
                    logger.exception(
                        "Failed to write runner-installed.timestamp into shared filesystem "
                        "for runner %s, will not be able to issue all metrics.",
                        runner.config.name,
                    )

        else:
            runner.create(
                config=CreateRunnerConfig(
                    image=self.config.image,
                    resources=resources,
                    binary_path=RunnerManager.runner_bin_path,
                    registration_token=registration_token,
                    arch=self.config.charm_state.arch,
                )
            )

    def _issue_runner_metrics(self) -> IssuedMetricEventsStats:
        """Issue runner metrics.

        Returns:
            The stats of issued metric events.
        """
        runner_states = self._get_runner_health_states()

        total_stats: IssuedMetricEventsStats = {}
        for extracted_metrics in runner_metrics.extract(ignore_runners=set(runner_states.healthy)):
            try:
                job_metrics = github_metrics.job(
                    github_client=self._clients.github,
                    pre_job_metrics=extracted_metrics.pre_job,
                    runner_name=extracted_metrics.runner_name,
                )
            except errors.GithubMetricsError:
                logger.exception("Failed to calculate job metrics")
                job_metrics = None

            issued_events = runner_metrics.issue_events(
                runner_metrics=extracted_metrics,
                job_metrics=job_metrics,
                flavor=self.app_name,
            )
            for event_type in issued_events:
                total_stats[event_type] = total_stats.get(event_type, 0) + 1
        return total_stats

    def _issue_reconciliation_metric(
        self,
        metric_stats: IssuedMetricEventsStats,
        reconciliation_start_ts: float,
        reconciliation_end_ts: float,
    ):
        """Issue reconciliation metric.

        Args:
            metric_stats: The stats of issued metric events.
            reconciliation_start_ts: The timestamp of when reconciliation started.
            reconciliation_end_ts: The timestamp of when reconciliation ended.
        """
        runners = self._get_runners()
        runner_states = self._get_runner_health_states()
        healthy_runners = set(runner_states.healthy)
        online_runners = [
            runner for runner in runners if runner.status.exist and runner.status.online
        ]
        active_runner_names = {
            runner.config.name for runner in online_runners if runner.status.busy
        }
        offline_runner_names = {
            runner.config.name
            for runner in runners
            if runner.status.exist and not runner.status.online
        }

        active_count = len(active_runner_names)
        idle_online_count = len(online_runners) - active_count
        idle_offline_count = len((offline_runner_names & healthy_runners) - active_runner_names)

        try:
            metrics.issue_event(
                event=metrics.Reconciliation(
                    timestamp=time.time(),
                    flavor=self.app_name,
                    crashed_runners=metric_stats.get(metrics.RunnerStart, 0)
                    - metric_stats.get(metrics.RunnerStop, 0),
                    idle_runners=idle_online_count + idle_offline_count,
                    duration=reconciliation_end_ts - reconciliation_start_ts,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue Reconciliation metric")

    def _get_runner_config(self, name: str) -> RunnerConfig:
        """Get the configuration for a runner.

        Sets the proxy settings for the runner according to the configuration
        and creates a new runner configuration object.

        Args:
            name: Name of the runner.

        Returns:
            Configuration for the runner.
        """
        if self.proxies and not self.proxies.use_aproxy:
            # If the proxy setting are set, then add NO_PROXY local variables.
            if self.proxies.no_proxy:
                no_proxy = f"{self.proxies.no_proxy},"
            else:
                no_proxy = ""
            no_proxy = f"{no_proxy}{name},.svc"

            proxies = RunnerProxySetting(
                no_proxy=no_proxy,
                http=self.proxies.http,
                https=self.proxies.https,
                aproxy_address=None,
            )
        elif self.proxies.use_aproxy:
            proxies = RunnerProxySetting(
                aproxy_address=self.proxies.aproxy_address, no_proxy=None, http=None, https=None
            )
        else:
            proxies = None

        return RunnerConfig(
            app_name=self.app_name,
            dockerhub_mirror=self.config.dockerhub_mirror,
            issue_metrics=self.config.are_metrics_enabled,
            labels=self.config.charm_state.charm_config.labels,
            lxd_storage_path=self.config.lxd_storage_path,
            path=self.config.path,
            proxies=proxies,
            name=name,
            ssh_debug_connections=self.config.charm_state.ssh_debug_connections,
        )

    def _spawn_new_runners(self, count: int, resources: VirtualMachineResources):
        """Spawn new runners.

        Args:
            count: Number of runners to spawn.
            resources: Configuration of the virtual machine resources.
        """
        if not RunnerManager.runner_bin_path.exists():
            raise RunnerCreateError("Unable to create runner due to missing runner binary.")
        logger.info("Getting registration token for GitHub runners.")
        registration_token = self._clients.github.get_runner_registration_token(self.config.path)
        remove_token = self._clients.github.get_runner_remove_token(self.config.path)
        logger.info("Attempting to add %i runner(s).", count)
        for _ in range(count):
            config = self._get_runner_config(self._generate_runner_name())
            runner = Runner(self._clients, config, RunnerStatus())
            try:
                self._create_runner(registration_token, resources, runner)
                logger.info("Created runner: %s", runner.config.name)
            except RunnerCreateError:
                logger.error("Unable to create runner: %s", runner.config.name)
                runner.remove(remove_token)
                logger.info("Cleaned up runner: %s", runner.config.name)
                raise

    def _remove_runners(self, count: int, runners: list[Runner]) -> None:
        """Remove runners.

        Args:
            count: Number of runners to remove.
            runners: List of online runners.
        """
        logger.info("Attempting to remove %i runner(s).", count)
        # Idle runners are online runners that have not taken a job.
        idle_runners = [runner for runner in runners if not runner.status.busy]
        offset = min(count, len(idle_runners))
        if offset != 0:
            logger.info("Removing %i runner(s).", offset)
            remove_runners = idle_runners[:offset]

            logger.info("Cleaning up idle runners.")

            remove_token = self._clients.github.get_runner_remove_token(self.config.path)

            for runner in remove_runners:
                runner.remove(remove_token)
                logger.info(REMOVED_RUNNER_LOG_STR, runner.config.name)
        else:
            logger.info("There are no idle runners to remove.")

    def reconcile(self, quantity: int, resources: VirtualMachineResources) -> int:
        """Bring runners in line with target.

        Args:
            quantity: Number of intended runners.
            resources: Configuration of the virtual machine resources.

        Returns:
            Difference between intended runners and actual runners.
        """
        if self.config.are_metrics_enabled:
            start_ts = time.time()

        runners = self._get_runners()

        # Add/Remove runners to match the target quantity
        online_runners = [
            runner for runner in runners if runner.status.exist and runner.status.online
        ]

        runner_states = self._get_runner_health_states()

        logger.info(
            (
                "Expected runner count: %i, Online count: %i, Offline count: %i, "
                "healthy count: %i, unhealthy count: %i"
            ),
            quantity,
            len(online_runners),
            len(runners) - len(online_runners),
            len(runner_states.healthy),
            len(runner_states.unhealthy),
        )

        runner_logs.remove_outdated_crashed()
        if self.config.are_metrics_enabled:
            metric_stats = self._issue_runner_metrics()

        # Clean up offline runners
        if runner_states.unhealthy:
            logger.info("Cleaning up unhealthy runners.")

            remove_token = self._clients.github.get_runner_remove_token(self.config.path)

            unhealthy_runners = [
                runner for runner in runners if runner.config.name in set(runner_states.unhealthy)
            ]

            for runner in unhealthy_runners:
                if self.config.are_metrics_enabled:
                    try:
                        runner_logs.get_crashed(runner)
                    except errors.RunnerLogsError:
                        logger.exception(
                            "Failed to get logs of crashed runner %s", runner.config.name
                        )
                runner.remove(remove_token)
                logger.info(REMOVED_RUNNER_LOG_STR, runner.config.name)

        delta = quantity - len(runner_states.healthy)
        # Spawn new runners
        if delta > 0:
            self._spawn_new_runners(delta, resources)
        elif delta < 0:
            self._remove_runners(count=-delta, runners=online_runners)
        else:
            logger.info("No changes to number of runners needed.")

        if self.config.are_metrics_enabled:
            end_ts = time.time()
            self._issue_reconciliation_metric(
                metric_stats=metric_stats,
                reconciliation_start_ts=start_ts,
                reconciliation_end_ts=end_ts,
            )
        return delta

    def _runners_in_pre_job(self) -> bool:
        """Check there exist runners in the pre-job script stage.

        If a runner has taken a job for 1 minute or more, it is assumed to exit the pre-job script.

        Returns:
            Whether there are runners that has taken a job and run for less than 1 minute.
        """
        now = datetime.now(timezone.utc)
        busy_runners = [
            runner for runner in self._get_runners() if runner.status.exist and runner.status.busy
        ]
        for runner in busy_runners:
            # Check if `_work` directory exists, if it exists the runner has started a job.
            exit_code, stdout, _ = runner.instance.execute(
                ["/usr/bin/stat", "-c", "'%w'", "/home/ubuntu/github-runner/_work"]
            )
            if exit_code != 0:
                return False
            # The date is between two single quotes(').
            _, output, _ = stdout.read().decode("utf-8").strip().split("'")
            date_str, time_str, timezone_str = output.split(" ")
            timezone_str = f"{timezone_str[:3]}:{timezone_str[3:]}"
            job_start_time = datetime.fromisoformat(f"{date_str}T{time_str[:12]}{timezone_str}")
            if job_start_time + timedelta(minutes=1) > now:
                return False
        return True

    def flush(self, mode: FlushMode = FlushMode.FLUSH_IDLE) -> int:
        """Remove existing runners.

        Args:
            mode: Strategy for flushing runners.

        Returns:
            Number of runners removed.
        """
        try:
            remove_token = self._clients.github.get_runner_remove_token(self.config.path)
        except errors.GithubClientError:
            logger.exception("Failed to get remove-token to unregister runners from GitHub.")
            if mode != FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK:
                raise
            logger.info("Proceeding with flush without remove-token.")
            remove_token = None

        # Removing non-busy runners
        runners = [
            runner
            for runner in self._get_runners()
            if runner.status.exist and not runner.status.busy
        ]

        logger.info("Removing existing %i non-busy local runners", len(runners))

        remove_count = len(runners)
        for runner in runners:
            runner.remove(remove_token)
            logger.info(REMOVED_RUNNER_LOG_STR, runner.config.name)

        if mode in (
            FlushMode.FLUSH_IDLE_WAIT_REPO_CHECK,
            FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK,
            FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK,
        ):
            for _ in range(5):
                if not self._runners_in_pre_job():
                    break
                time.sleep(30)
            else:
                logger.warning(
                    (
                        "Proceed with flush runner after timeout waiting on runner in setup "
                        "stage, pre-job script might fail in currently running jobs"
                    )
                )

        if mode in {
            FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK,
            FlushMode.FLUSH_BUSY,
            FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK,
        }:
            busy_runners = [runner for runner in self._get_runners() if runner.status.exist]

            logger.info("Removing existing %i busy local runners", len(runners))

            remove_count += len(busy_runners)
            for runner in busy_runners:
                runner.remove(remove_token)
                logger.info(REMOVED_RUNNER_LOG_STR, runner.config.name)

        return remove_count

    def _generate_runner_name(self) -> str:
        """Generate a runner name based on charm name.

        Returns:
            Generated name of runner.
        """
        suffix = secrets.token_hex(12)
        return f"{self.instance_name}-{suffix}"

    def _get_runner_github_info(self) -> Dict[str, SelfHostedRunner]:
        remote_runners_list: list[SelfHostedRunner] = self._clients.github.get_runner_github_info(
            self.config.path
        )

        logger.debug("List of runners found on GitHub:%s", remote_runners_list)

        return {
            runner.name: runner
            for runner in remote_runners_list
            if runner.name.startswith(f"{self.instance_name}-")
        }

    def _get_runners(self) -> list[Runner]:
        """Query for the list of runners.

        Returns:
            List of `Runner` from information on LXD or GitHub.
        """

        def create_runner_info(
            name: str,
            local_runner: Optional[LxdInstance],
            remote_runner: Optional[SelfHostedRunner],
        ) -> Runner:
            """Create runner from information from GitHub and LXD."""
            logger.debug(
                (
                    "Found runner %s with GitHub info [status: %s, busy: %s, labels: %s] and LXD "
                    "info [status: %s]"
                ),
                name,
                getattr(remote_runner, "status", None),
                getattr(remote_runner, "busy", None),
                getattr(remote_runner, "labels", None),
                getattr(local_runner, "status", None),
            )

            runner_id = getattr(remote_runner, "id", None)
            running = local_runner is not None
            online = getattr(remote_runner, "status", None) == "online"
            busy = getattr(remote_runner, "busy", None)

            config = self._get_runner_config(name)
            return Runner(
                self._clients,
                config,
                RunnerStatus(runner_id, running, online, busy),
                local_runner,
            )

        remote_runners = self._get_runner_github_info()
        local_runners = {
            instance.name: instance
            # Pylint cannot find the `all` method.
            for instance in self._clients.lxd.instances.all()  # pylint: disable=no-member
            if instance.name.startswith(f"{self.instance_name}-")
        }

        runners: list[Runner] = []
        for name in set(local_runners.keys()) | set(remote_runners.keys()):
            runners.append(
                create_runner_info(name, local_runners.get(name), remote_runners.get(name))
            )

        return runners

    def _build_image_command(self) -> list[str]:
        """Get command for building runner image.

        Returns:
            Command to execute to build runner image.
        """
        http_proxy = self.proxies.http or ""
        https_proxy = self.proxies.https or ""
        no_proxy = self.proxies.no_proxy or ""

        cmd = [
            "/usr/bin/bash",
            str(BUILD_IMAGE_SCRIPT_FILENAME.absolute()),
            http_proxy,
            https_proxy,
            no_proxy,
        ]
        if LXD_PROFILE_YAML.exists():
            cmd += ["test"]
        return cmd

    def build_runner_image(self) -> None:
        """Build the LXD image for hosting runner.

        Build container image in test mode, else virtual machine image.

        Raises:
            LxdError: Unable to build the LXD image.
        """
        execute_command(self._build_image_command())

    def schedule_build_runner_image(self) -> None:
        """Install cron job for building runner image."""
        # Replace empty string in the build image command list and form a string.
        build_image_command = " ".join(
            [part if part else "''" for part in self._build_image_command()]
        )

        cron_file = self.cron_path / "build-runner-image"
        # Randomized the time executing the building of image to prevent all instances of the charm
        # building images at the same time, using up the disk, and network IO of the server.
        # The random number are not used for security purposes.
        minute = random.randint(0, 59)  # nosec B311
        base_hour = random.randint(0, 5)  # nosec B311
        hours = ",".join([str(base_hour + offset) for offset in (0, 6, 12, 18)])
        cron_file.write_text(f"{minute} {hours} * * * ubuntu {build_image_command}\n")
