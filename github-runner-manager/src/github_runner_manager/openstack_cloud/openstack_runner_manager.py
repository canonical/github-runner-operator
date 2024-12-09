# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for self-hosted runner on OpenStack."""

import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import fabric
import invoke
import jinja2
import paramiko
import paramiko.ssh_exception
from fabric import Connection as SSHConnection

from github_runner_manager.errors import (
    CreateMetricsStorageError,
    GetMetricsStorageError,
    KeyfileError,
    MissingServerConfigError,
    OpenStackError,
    OpenstackHealthCheckError,
    RunnerCreateError,
    RunnerStartError,
    SSHError,
)
from github_runner_manager.manager.cloud_runner_manager import (
    CloudInitStatus,
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    GitHubRunnerConfig,
    InstanceId,
    SupportServiceConfig,
)
from github_runner_manager.manager.runner_manager import HealthState
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics import storage as metrics_storage
from github_runner_manager.metrics.storage import StorageManager
from github_runner_manager.openstack_cloud import health_checks
from github_runner_manager.openstack_cloud.constants import (
    CREATE_SERVER_TIMEOUT,
    METRICS_EXCHANGE_PATH,
    RUNNER_LISTENER_PROCESS,
    RUNNER_WORKER_PROCESS,
)
from github_runner_manager.openstack_cloud.openstack_cloud import (
    OpenstackCloud,
    OpenStackCredentials,
    OpenstackInstance,
)
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient
from github_runner_manager.types_ import SystemUserConfig
from github_runner_manager.types_.github import GitHubOrg
from github_runner_manager.utilities import retry, set_env_var

logger = logging.getLogger(__name__)

BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"
_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"
MAX_METRICS_FILE_SIZE = 1024

RUNNER_STARTUP_PROCESS = "/home/ubuntu/actions-runner/run.sh"

OUTDATED_METRICS_STORAGE_IN_SECONDS = CREATE_SERVER_TIMEOUT + 30  # add a bit on top of the timeout

HEALTH_CHECK_ERROR_LOG_MSG = "Health check could not be completed for %s"


class _GithubRunnerRemoveError(Exception):
    """Represents an error while SSH into a runner and running the remove script."""


class _PullFileError(Exception):
    """Represents an error while pulling a file from the runner instance."""


@dataclass
class OpenStackServerConfig:
    """Configuration for OpenStack server.

    Attributes:
        image: The image name for runners to use.
        flavor: The flavor name for runners to use.
        network: The network name for runners to use.
    """

    image: str
    flavor: str
    network: str


@dataclass
class OpenStackRunnerManagerConfig:
    """Configuration for OpenStack runner manager.

    Attributes:
        name: The name of the manager.
        prefix: The prefix of the runner names.
        credentials: The OpenStack authorization information.
        server_config: The configuration for OpenStack server.
        runner_config: The configuration for the GitHub runner.
        service_config: The configuration for supporting services.
        system_user_config: The user to use for creating metrics storage.
    """

    name: str
    prefix: str
    credentials: OpenStackCredentials
    server_config: OpenStackServerConfig | None
    runner_config: GitHubRunnerConfig
    service_config: SupportServiceConfig
    system_user_config: SystemUserConfig


@dataclass
class _RunnerHealth:
    """Runners with health state.

    Attributes:
        healthy: The list of healthy runners.
        unhealthy:  The list of unhealthy runners.
        unknown: The list of runners whose health state could not be determined.
    """

    healthy: tuple[OpenstackInstance, ...]
    unhealthy: tuple[OpenstackInstance, ...]
    unknown: tuple[OpenstackInstance, ...]


class OpenStackRunnerManager(CloudRunnerManager):
    """Manage self-hosted runner on OpenStack cloud.

    Attributes:
        name_prefix: The name prefix of the runners created.
    """

    def __init__(
        self,
        config: OpenStackRunnerManagerConfig,
    ) -> None:
        """Construct the object.

        Args:
            config: The configuration for the openstack runner manager.
        """
        self._config = config
        self._credentials = config.credentials
        self._openstack_cloud = OpenstackCloud(
            credentials=self._credentials,
            prefix=self.name_prefix,
            system_user=config.system_user_config.user,
        )
        self._system_user_config = config.system_user_config
        self._metrics_storage_manager = metrics_storage.StorageManager(
            system_user_config=config.system_user_config
        )

        # Setting the env var to this process and any child process spawned.
        proxies = config.service_config.proxy_config
        if proxies and (no_proxy := proxies.no_proxy):
            set_env_var("NO_PROXY", no_proxy)
        if proxies and (http_proxy := proxies.http):
            set_env_var("HTTP_PROXY", http_proxy)
        if proxies and (https_proxy := proxies.https):
            set_env_var("HTTPS_PROXY", https_proxy)

    @property
    def name_prefix(self) -> str:
        """The prefix of runner names.

        Returns:
            The prefix of the runner names managed by this class.
        """
        return self._config.prefix

    def create_runner(self, registration_token: str) -> InstanceId:
        """Create a self-hosted runner.

        Args:
            registration_token: The GitHub registration token for registering runners.

        Raises:
            MissingServerConfigError: Unable to create runner due to missing configuration.
            RunnerCreateError: Unable to create runner due to OpenStack issues.

        Returns:
            Instance ID of the runner.
        """
        if (server_config := self._config.server_config) is None:
            raise MissingServerConfigError("Missing server configuration to create runners")

        start_timestamp = time.time()
        instance_id = OpenStackRunnerManager._generate_instance_id()
        instance_name = self._openstack_cloud.get_server_name(instance_id=instance_id)
        self._init_metrics_storage(name=instance_name, install_start_timestamp=start_timestamp)

        cloud_init = self._generate_cloud_init(
            instance_name=instance_name, registration_token=registration_token
        )
        try:
            instance = self._openstack_cloud.launch_instance(
                instance_id=instance_id,
                image=server_config.image,
                flavor=server_config.flavor,
                network=server_config.network,
                cloud_init=cloud_init,
            )
        except OpenStackError as err:
            raise RunnerCreateError(f"Failed to create {instance_name} openstack runner") from err

        logger.debug("Waiting for runner process to startup: %s", instance.server_name)
        self._wait_runner_startup(instance)
        logger.debug("Waiting for runner process to be running: %s", instance.server_name)
        self._wait_runner_running(instance)

        logger.info("Runner %s created successfully", instance.server_name)
        return instance_id

    def get_runner(self, instance_id: InstanceId) -> CloudRunnerInstance | None:
        """Get a self-hosted runner by instance id.

        Args:
            instance_id: The instance id.

        Returns:
            Information on the runner instance.
        """
        logger.debug("Getting runner info %s", instance_id)
        instance = self._openstack_cloud.get_instance(instance_id)
        logger.debug(
            "Runner info fetched, checking health %s %s", instance_id, instance.server_name
        )

        try:
            healthy = health_checks.check_runner(
                openstack_cloud=self._openstack_cloud, instance=instance
            )
            logger.debug("Runner health check completed %s %s", instance.server_name, healthy)
        except OpenstackHealthCheckError:
            logger.exception(HEALTH_CHECK_ERROR_LOG_MSG, instance.server_name)
            healthy = None
        return (
            CloudRunnerInstance(
                name=instance.server_name,
                instance_id=instance_id,
                health=HealthState.from_value(healthy),
                state=CloudRunnerState.from_openstack_server_status(instance.status),
            )
            if instance is not None
            else None
        )

    def get_runners(
        self, states: Sequence[CloudRunnerState] | None = None
    ) -> tuple[CloudRunnerInstance, ...]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.

        Returns:
            Information on the runner instances.
        """
        instances = self._openstack_cloud.get_instances()
        runners = []
        for instance in instances:
            try:
                healthy = health_checks.check_runner(
                    openstack_cloud=self._openstack_cloud, instance=instance
                )
            except OpenstackHealthCheckError:
                logger.exception(HEALTH_CHECK_ERROR_LOG_MSG, instance.server_name)
                healthy = None
            runners.append(
                CloudRunnerInstance(
                    name=instance.server_name,
                    instance_id=instance.instance_id,
                    health=HealthState.from_value(healthy),
                    state=CloudRunnerState.from_openstack_server_status(instance.status),
                )
            )
        if states is None:
            return tuple(runners)

        state_set = set(states)
        return tuple(runner for runner in runners if runner.state in state_set)

    def delete_runner(
        self, instance_id: InstanceId, remove_token: str
    ) -> runner_metrics.RunnerMetrics | None:
        """Delete self-hosted runners.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.

        Returns:
            Any metrics collected during the deletion of the runner.
        """
        logger.debug("Delete instance %s", instance_id)
        instance = self._openstack_cloud.get_instance(instance_id)
        if instance is None:
            logger.warning(
                "Unable to delete instance %s as it is not found",
                self._openstack_cloud.get_server_name(instance_id),
            )
            return None

        logger.debug(
            "Metrics extracted, deleting instance %s %s", instance_id, instance.server_name
        )
        self._delete_runner(instance, remove_token)
        logger.debug("Instance deleted successfully %s %s", instance_id, instance.server_name)
        logger.debug("Extract metrics for runner %s %s", instance_id, instance.server_name)
        extracted_metrics = runner_metrics.extract(
            metrics_storage_manager=self._metrics_storage_manager,
            runners={instance.server_name},
            include=True,
        )
        return next(extracted_metrics, None)

    def flush_runners(
        self, remove_token: str, busy: bool = False
    ) -> Iterator[runner_metrics.RunnerMetrics]:
        """Remove idle and/or busy runners.

        Args:
            remove_token:
            busy: If false, only idle runners are removed. If true, both idle and busy runners are
                removed.

        Returns:
            Any metrics retrieved from flushed runners.
        """
        instance_list = self._openstack_cloud.get_instances()
        for instance in instance_list:
            try:
                logger.debug(
                    "Checking runner state and flushing %s %s",
                    instance.server_id,
                    instance.server_name,
                )
                self._check_state_and_flush(instance, busy)
            except SSHError:
                logger.warning(
                    "Unable to determine state of  %s and kill runner process due to SSH issues",
                    instance.server_name,
                )
                continue
        logger.debug("Runners successfully flushed, cleaning up.")
        return self.cleanup(remove_token)

    def cleanup(self, remove_token: str) -> Iterator[runner_metrics.RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Args:
            remove_token: The GitHub remove token.

        Returns:
            Any metrics retrieved from cleanup runners.
        """
        logger.debug("Getting runner healths for cleanup.")
        runners = self._get_runners_health()

        healthy_runner_names = {runner.server_name for runner in runners.healthy}
        unhealthy_runner_names = {runner.server_name for runner in runners.unhealthy}
        unknown_runner_names = {runner.server_name for runner in runners.unknown}
        logger.debug("Healthy runners: %s", healthy_runner_names)
        logger.debug("Unhealthy runners: %s", unhealthy_runner_names)
        logger.debug("Unknown health runners: %s", unknown_runner_names)

        logger.debug("Deleting unhealthy runners.")
        for runner in runners.unhealthy:
            self._delete_runner(runner, remove_token)
        logger.debug("Cleaning up runner resources.")
        self._openstack_cloud.cleanup()
        logger.debug("Cleanup completed successfully.")

        logger.debug("Extracting metrics.")
        return self._cleanup_extract_metrics(
            metrics_storage_manager=self._metrics_storage_manager,
            ignore_runner_names=healthy_runner_names | unknown_runner_names,
            include_runner_names=unhealthy_runner_names,
        )

    @staticmethod
    def _cleanup_extract_metrics(
        metrics_storage_manager: StorageManager,
        ignore_runner_names: set[str],
        include_runner_names: set[str],
    ) -> Iterator[runner_metrics.RunnerMetrics]:
        """Extract metrics for certain runners and dangling metrics storage.

        Args:
            metrics_storage_manager: The metrics storage manager.
            ignore_runner_names: The names of the runners whose metrics should not be extracted.
            include_runner_names: The names of the runners whose metrics should be extracted.

        Returns:
            Any metrics retrieved from the include_runner_names and dangling storage.
        """
        # There may be runners under construction that are not included in the runner_names sets
        # because they do not yet exist in OpenStack and that should not be cleaned up.
        # On the other hand, there could be storage for runners from the past that
        # should be cleaned up.
        all_runner_names = ignore_runner_names | include_runner_names
        unmatched_metrics_storage = (
            ms
            for ms in metrics_storage_manager.list_all()
            if ms.runner_name not in all_runner_names
        )
        # We assume that storage is dangling if it has not been updated for a long time.
        dangling_storage_runner_names = {
            ms.runner_name
            for ms in unmatched_metrics_storage
            if ms.path.stat().st_mtime < time.time() - OUTDATED_METRICS_STORAGE_IN_SECONDS
        }
        return runner_metrics.extract(
            metrics_storage_manager=metrics_storage_manager,
            runners=include_runner_names | dangling_storage_runner_names,
            include=True,
        )

    def _delete_runner(self, instance: OpenstackInstance, remove_token: str) -> None:
        """Delete self-hosted runners by openstack instance.

        Args:
            instance: The OpenStack instance.
            remove_token: The GitHub remove token.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
            self._pull_runner_metrics(instance.server_name, ssh_conn)

            try:
                OpenStackRunnerManager._run_runner_removal_script(
                    instance.server_name, ssh_conn, remove_token
                )
            except _GithubRunnerRemoveError:
                logger.warning(
                    "Unable to run github runner removal script for %s",
                    instance.server_name,
                    stack_info=True,
                )
        except SSHError:
            logger.exception(
                "Failed to get SSH connection while removing %s", instance.server_name
            )
            logger.warning(
                "Skipping runner remove script for %s due to SSH issues", instance.server_name
            )

        try:
            self._openstack_cloud.delete_instance(instance.instance_id)
        except OpenStackError:
            logger.exception(
                "Unable to delete openstack instance for runner %s", instance.server_name
            )

    def _get_runners_health(self) -> _RunnerHealth:
        """Get runners by health state.

        Returns:
            Runners by health state.
        """
        runner_list = self._openstack_cloud.get_instances()

        healthy, unhealthy, unknown = [], [], []
        for runner in runner_list:
            try:
                if health_checks.check_runner(
                    openstack_cloud=self._openstack_cloud, instance=runner
                ):
                    healthy.append(runner)
                else:
                    unhealthy.append(runner)
            except OpenstackHealthCheckError:
                logger.exception(HEALTH_CHECK_ERROR_LOG_MSG, runner.server_name)
                unknown.append(runner)
        return _RunnerHealth(
            healthy=tuple(healthy), unhealthy=tuple(unhealthy), unknown=tuple(unknown)
        )

    def _generate_cloud_init(self, instance_name: str, registration_token: str) -> str:
        """Generate cloud init userdata.

        This is the script the openstack server runs on startup.

        Args:
            instance_name: The name of the instance.
            registration_token: The GitHub runner registration token.

        Returns:
            The cloud init userdata for openstack instance.
        """
        jinja = jinja2.Environment(
            loader=jinja2.PackageLoader("github_runner_manager", "templates"), autoescape=True
        )

        service_config = self._config.service_config
        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(PRE_JOB_SCRIPT),
            dockerhub_mirror=service_config.dockerhub_mirror or "",
            ssh_debug_info=(
                secrets.choice(service_config.ssh_debug_connections)
                if service_config.ssh_debug_connections
                else None
            ),
        )

        pre_job_contents_dict = {
            "issue_metrics": True,
            "metrics_exchange_path": str(METRICS_EXCHANGE_PATH),
            "do_repo_policy_check": False,
        }
        repo_policy = self._get_repo_policy_compliance_client()
        if repo_policy is not None:
            pre_job_contents_dict.update(
                {
                    "repo_policy_base_url": repo_policy.base_url,
                    "repo_policy_one_time_token": repo_policy.get_one_time_token(),
                    "do_repo_policy_check": True,
                }
            )

        pre_job_contents = jinja.get_template("pre-job.j2").render(pre_job_contents_dict)

        runner_group = None
        runner_config = self._config.runner_config
        if isinstance(runner_config.github_path, GitHubOrg):
            runner_group = runner_config.github_path.group
        aproxy_address = (
            service_config.proxy_config.aproxy_address
            if service_config.proxy_config is not None
            else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            github_url=f"https://github.com/{runner_config.github_path.path()}",
            runner_group=runner_group,
            token=registration_token,
            instance_labels=",".join(runner_config.labels),
            instance_name=instance_name,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=service_config.dockerhub_mirror,
        )

    def _get_repo_policy_compliance_client(self) -> RepoPolicyComplianceClient | None:
        """Get repo policy compliance client.

        Returns:
            The repo policy compliance client.
        """
        if (service_config := self._config.service_config).repo_policy_compliance is not None:
            return RepoPolicyComplianceClient(
                service_config.repo_policy_compliance.url,
                service_config.repo_policy_compliance.token,
            )
        return None

    @retry(tries=3, delay=5, backoff=2, local_logger=logger)
    def _check_state_and_flush(self, instance: OpenstackInstance, busy: bool) -> None:
        """Kill runner process depending on idle or busy.

        Due to update to runner state has some delay with GitHub API. The state of the runner is
        determined by which runner processes are running. If the Runner.Worker process is running,
        the runner is deemed to be busy.

        Raises:
            SSHError: Unable to check the state of the runner and kill the runner process due to
                SSH failure.

        Args:
            instance: The openstack instance to kill the runner process.
            busy: Kill the process if runner is busy, else only kill runner
                process if runner is idle.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except KeyfileError:
            logger.exception(
                "Health check failed due to unable to find keyfile for %s", instance.server_name
            )
            return
        except SSHError:
            logger.exception(
                "SSH connection failure with %s during flushing", instance.server_name
            )
            raise

        # Using a single command to determine the state and kill the process if needed.
        # This makes it more robust when network is unstable.
        if busy:
            logger.info("Attempting to kill all runner process on %s", instance.server_name)
            # kill both Runner.Listener and Runner.Worker processes.
            # This kills pre-job.sh, a child process of Runner.Worker.
            kill_command = (
                f"pgrep -x {RUNNER_LISTENER_PROCESS} && "
                f"kill $(pgrep -x {RUNNER_LISTENER_PROCESS});"
                f"pgrep -x {RUNNER_WORKER_PROCESS} && kill $(pgrep -x {RUNNER_WORKER_PROCESS});"
            )
        else:
            logger.info(
                "Attempting to kill runner process on %s if not busy", instance.server_name
            )
            # Only kill Runner.Listener if Runner.Worker does not exist.
            kill_command = (
                f"! pgrep -x {RUNNER_WORKER_PROCESS} && pgrep -x {RUNNER_LISTENER_PROCESS} && "
                f"kill $(pgrep -x {RUNNER_LISTENER_PROCESS})"
            )
        logger.info("Running kill process command: %s", kill_command)
        # Checking the result of kill command is not useful, as the exit code does not reveal much.
        result: fabric.Result = ssh_conn.run(kill_command, warn=True, timeout=30)
        logger.info(
            "Kill process command output, ok: %s code %s, out: %s, err: %s",
            result.ok,
            result.return_code,
            result.stdout,
            result.stderr,
        )

    @retry(tries=10, delay=60, local_logger=logger)
    def _wait_runner_startup(self, instance: OpenstackInstance) -> None:
        """Wait until runner is startup.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner startup process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH to {instance.server_name} during creation possible due to setup "
                "not completed"
            ) from err

        logger.debug("Running `cloud-init status` on instance %s.", instance.server_name)
        result: invoke.runners.Result = ssh_conn.run("cloud-init status", warn=True, timeout=60)
        if not result.ok:
            logger.warning(
                "cloud-init status command failed on %s: %s.", instance.server_name, result.stderr
            )
            raise RunnerStartError(f"Runner startup process not found on {instance.server_name}")
        # A short running job may have already completed and exited the runner, hence check the
        # condition via cloud-init status check.
        if CloudInitStatus.DONE in result.stdout:
            return
        logger.debug("Running `ps aux` on instance %s.", instance.server_name)
        result = ssh_conn.run("ps aux", warn=True, timeout=60)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s", instance.server_name)
            raise RunnerStartError(f"Unable to SSH run `ps aux` on {instance.server_name}")
        # Runner startup process is the parent process of runner.Listener and runner.Worker which
        # starts up much faster.
        if RUNNER_STARTUP_PROCESS not in result.stdout:
            logger.warning("Runner startup process not found on %s", instance.server_name)
            raise RunnerStartError(f"Runner startup process not found on {instance.server_name}")
        logger.info("Runner startup process found to be healthy on %s", instance.server_name)

    @retry(tries=5, delay=60, local_logger=logger)
    def _wait_runner_running(self, instance: OpenstackInstance) -> None:
        """Wait until runner is running.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH connect to {instance.server_name} openstack runner"
            ) from err

        try:
            healthy = health_checks.check_active_runner(
                ssh_conn=ssh_conn, instance=instance, accept_finished_job=True
            )
        except OpenstackHealthCheckError as exc:
            raise RunnerStartError(
                f"Failed to check health of runner process on {instance.server_name}"
            ) from exc
        if not healthy:
            logger.info("Runner %s not considered healthy", instance.server_name)
            raise RunnerStartError(
                f"Runner {instance.server_name} failed to initialize after starting"
            )

        logger.info("Runner %s found to be healthy", instance.server_name)

    @staticmethod
    def _generate_instance_id() -> InstanceId:
        r"""Generate an instance id suffix compliant to the GitHub runner naming convention.

        The GitHub runner name convention is as following:
        A valid runner name is 64 characters or less in length and does not include '"', '/', ':',
        '<', '>', '\', '|', '*' and '?'.

        The collision rate calculation:
        alphanumeric 12 chars long (26 alphabet + 10 digits = 36)
        36^12 is big enough for our use-case.

        Return:
            The id.
        """
        return secrets.token_hex(6)

    def _init_metrics_storage(self, name: str, install_start_timestamp: float) -> None:
        """Create metrics storage for runner.

        An error will be logged if the storage cannot be created.
        It is assumed that the code will not be able to issue metrics for this runner
        and not fail for other operations.

        Args:
            name: The name of the runner.
            install_start_timestamp: The timestamp of installation start.
        """
        try:
            storage = self._metrics_storage_manager.create(runner_name=name)
        except CreateMetricsStorageError:
            logger.exception(
                "Failed to create metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
        else:
            try:
                (storage.path / runner_metrics.RUNNER_INSTALLATION_START_TS_FILE_NAME).write_text(
                    str(install_start_timestamp), encoding="utf-8"
                )
            except FileNotFoundError:
                logger.exception(
                    f"Failed to write {runner_metrics.RUNNER_INSTALLATION_START_TS_FILE_NAME}"
                    f" into metrics storage for runner %s, will not be able to issue all metrics.",
                    name,
                )

    def _pull_runner_metrics(self, name: str, ssh_conn: SSHConnection) -> None:
        """Pull metrics from runner.

        Args:
            name: The name of the runner.
            ssh_conn: The SSH connection to the runner.
        """
        logger.debug("Pulling metrics for %s", name)
        try:
            storage = self._metrics_storage_manager.get(runner_name=name)
        except GetMetricsStorageError:
            logger.exception(
                "Failed to get shared metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
            return

        try:
            OpenStackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "runner-installed.timestamp"),
                local_path=str(storage.path / runner_metrics.RUNNER_INSTALLED_TS_FILE_NAME),
                max_size=MAX_METRICS_FILE_SIZE,
            )
            OpenStackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "pre-job-metrics.json"),
                local_path=str(storage.path / runner_metrics.PRE_JOB_METRICS_FILE_NAME),
                max_size=MAX_METRICS_FILE_SIZE,
            )
            OpenStackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "post-job-metrics.json"),
                local_path=str(storage.path / runner_metrics.POST_JOB_METRICS_FILE_NAME),
                max_size=MAX_METRICS_FILE_SIZE,
            )
        except _PullFileError as exc:
            logger.warning(
                "Failed to pull metrics for %s: %s . Will not be able to issue all metrics",
                name,
                exc,
            )

    @staticmethod
    def _ssh_pull_file(
        ssh_conn: SSHConnection, remote_path: str, local_path: str, max_size: int
    ) -> None:
        """Pull file from the runner instance.

        Args:
            ssh_conn: The SSH connection instance.
            remote_path: The file path on the runner instance.
            local_path: The local path to store the file.
            max_size: If the file is larger than this, it will not be pulled.

        Raises:
            _PullFileError: Unable to pull the file from the runner instance.
            SSHError: Issue with SSH connection.
        """
        try:
            result = ssh_conn.run(f"stat -c %s {remote_path}", warn=True, timeout=60)
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
        if not result.ok:
            logger.warning(
                (
                    "Unable to get file size of %s on instance %s, "
                    "exit code: %s, stdout: %s, stderr: %s"
                ),
                remote_path,
                ssh_conn.host,
                result.return_code,
                result.stdout,
                result.stderr,
            )
            raise _PullFileError(f"Unable to get file size of {remote_path}")

        stdout = result.stdout
        try:
            stdout.strip()
            size = int(stdout)
            if size > max_size:
                raise _PullFileError(f"File size of {remote_path} too large {size} > {max_size}")
        except ValueError as exc:
            raise _PullFileError(f"Invalid file size for {remote_path}: stdout") from exc

        try:
            ssh_conn.get(remote=remote_path, local=local_path)
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
        except OSError as exc:
            raise _PullFileError(f"Unable to retrieve file {remote_path}") from exc

    @staticmethod
    def _run_runner_removal_script(
        instance_name: str, ssh_conn: SSHConnection, remove_token: str
    ) -> None:
        """Run Github runner removal script.

        Args:
            instance_name: The name of the runner instance.
            ssh_conn: The SSH connection to the runner instance.
            remove_token: The GitHub instance removal token.

        Raises:
            _GithubRunnerRemoveError: Unable to remove runner from GitHub.
        """
        try:
            result = ssh_conn.run(
                f"{_CONFIG_SCRIPT_PATH} remove --token {remove_token}", warn=True, timeout=60
            )
            if result.ok:
                return

            logger.warning(
                (
                    "Unable to run removal script on instance %s, "
                    "exit code: %s, stdout: %s, stderr: %s"
                ),
                instance_name,
                result.return_code,
                result.stdout,
                result.stderr,
            )
            raise _GithubRunnerRemoveError(f"Failed to remove runner {instance_name} from Github.")
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise _GithubRunnerRemoveError(
                f"Failed to remove runner {instance_name} from Github."
            ) from exc
