# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

import invoke
import jinja2
import paramiko
import paramiko.ssh_exception
from fabric import Connection as SshConnection

from charm_state import GithubOrg, GithubPath, ProxyConfig, SSHDebugConnection
from errors import (
    CreateMetricsStorageError,
    GetMetricsStorageError,
    IssueMetricEventError,
    OpenStackError,
    RunnerCreateError,
    RunnerError,
    RunnerRemoveError,
    RunnerStartError,
    SshError,
)
from manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    RunnerId,
)
from metrics import events as metric_events
from metrics import github as github_metrics
from metrics import runner as runner_metrics
from metrics import storage as metrics_storage
from openstack_cloud.openstack_cloud import OpenstackCloud, OpenstackInstance
from openstack_cloud.openstack_manager import GithubRunnerRemoveError
from repo_policy_compliance_client import RepoPolicyComplianceClient
from utilities import retry

logger = logging.getLogger(__name__)

BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME = "scripts/build-openstack-image.sh"
_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"
MAX_METRICS_FILE_SIZE = 1024

RUNNER_STARTUP_PROCESS = "/home/ubuntu/actions-runner/run.sh"
RUNNER_LISTENER_PROCESS = "Runner.Listener"
RUNNER_WORKER_PROCESS = "Runner.Worker"
CREATE_SERVER_TIMEOUT = 5 * 60


class _PullFileError(Exception):
    """Represents an error while pulling a file from the runner instance."""


@dataclass
class OpenstackRunnerManagerConfig:
    clouds_config: dict[str, dict]
    cloud: str
    image: str
    flavor: str
    network: str
    github_path: GithubPath
    labels: list[str]
    proxy_config: ProxyConfig | None
    dockerhub_mirror: str | None
    ssh_debug_connections: list[SSHDebugConnection] | None
    repo_policy_url: str | None
    repo_policy_token: str | None


class OpenstackRunnerManager(CloudRunnerManager):

    def __init__(self, prefix: str, config: OpenstackRunnerManagerConfig) -> None:
        self.prefix = prefix
        self.config = config
        self._openstack_cloud = OpenstackCloud(
            clouds_config=self.config.clouds_config,
            cloud=self.config.cloud,
            prefix=self.prefix,
        )

    def get_name_prefix(self) -> str:
        return self.prefix

    def create_runner(self, registration_token: str) -> RunnerId:
        start_timestamp = time.time()
        id = OpenstackRunnerManager._generate_runner_id()
        instance_name = self._openstack_cloud.get_server_name(instance_id=id)
        userdata = self._generate_userdata(
            instance_name=instance_name, registration_token=registration_token
        )
        try:
            instance = self._openstack_cloud.launch_instance(
                instance_id=id,
                image=self.config.image,
                flavor=self.config.flavor,
                network=self.config.network,
                userdata=userdata,
            )
        except OpenStackError as err:
            raise RunnerCreateError("Failed to create {instance_name} openstack runner") from err

        self._wait_runner_startup(instance)

        end_timestamp = time.time()
        OpenstackRunnerManager._issue_runner_installed_metric(
            name=instance_name,
            flavor=self.prefix,
            install_start_timestamp=start_timestamp,
            install_end_timestamp=end_timestamp,
        )
        return id

    def get_runner(self, id: RunnerId) -> CloudRunnerInstance | None:
        name = self._openstack_cloud.get_server_name(id)
        instances_list = self._openstack_cloud.get_instances()
        for instance in instances_list:
            if instance.server_name == name:
                return CloudRunnerInstance(
                    name=name,
                    id=id,
                    state=CloudRunnerState.from_openstack_server_status(instance.status),
                )
        return None

    def get_runners(
        self, states: Sequence[CloudRunnerState] | None = None
    ) -> Tuple[CloudRunnerInstance]:
        instances_list = self._openstack_cloud.get_instances()
        instances_list = [
            CloudRunnerInstance(
                name=instance.server_name,
                id=instance.instance_id,
                state=CloudRunnerState.from_openstack_server_status(instance.status),
            )
            for instance in instances_list
        ]
        if states is None:
            return instances_list
        return [instance for instance in instances_list if instance.state in states]

    def delete_runner(self, id: RunnerId, remove_token: str) -> None:
        instance = self._openstack_cloud.get_instance(id)
        self._delete_runner(instance, remove_token)

    def _delete_runner(self, instance: OpenstackInstance, remove_token) -> None:
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SshError:
            logger.exception("Failed SSH connection while removing %s", instance.server_name)
            raise RunnerRemoveError(f"Failed SSH connection for {instance.server_name}")
        self._pull_runner_metrics(instance.server_name, ssh_conn)
        try:
            OpenstackRunnerManager._run_github_runner_removal_script(
                instance.server_name, ssh_conn, remove_token
            )
        except GithubRunnerRemoveError:
            logger.warning(
                "Unable to run github runner removal script for %s",
                instance.server_name,
                stack_info=True,
            )

        try:
            self._openstack_cloud.delete_instance(id)
        except OpenStackError:
            logger.exception(
                "Unable to delete openstack instance for runner %s", instance.server_name
            )

    def cleanup(self, remove_token: str) -> None:
        runner_list = self._openstack_cloud.get_instances()

        for runner in runner_list:
            state = (CloudRunnerState(runner.status),)
            if state in (
                CloudRunnerState.DELETED,
                CloudRunnerState.ERROR,
                CloudRunnerState.STOPPED,
            ) or self._health_check(runner):
                self._delete_runner(runner, remove_token)

        self._openstack_cloud.cleanup()

    def _generate_userdata(self, instance_name: str, registration_token: str) -> str:
        jinja = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)

        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(PRE_JOB_SCRIPT),
            dockerhub_mirror=self.config.dockerhub_mirror or "",
            ssh_debug_info=(
                secrets.choice(self.config.ssh_debug_connections)
                if self.config.ssh_debug_connections
                else None
            ),
            # Proxies are handled by aproxy.
            proxies={},
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
        if isinstance(self.config.github_path, GithubOrg):
            runner_group = self.config.github_path.group
        aproxy_address = (
            self.config.proxy_config.aproxy_address
            if self.config.proxy_config is not None
            else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            github_url=f"https://github.com/{self.config.github_path.path()}",
            runner_group=runner_group,
            token=registration_token,
            instance_labels=",".join(self.config.labels),
            instance_name=instance_name,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=self.config.dockerhub_mirror,
        )

    def _get_repo_policy_compliance_client(self) -> RepoPolicyComplianceClient | None:
        if self.config.repo_policy_url and self.config.repo_policy_token:
            return RepoPolicyComplianceClient(
                self.config.repo_policy_url, self.config.repo_policy_token
            )
        return None

    def _health_check(self, instance: OpenstackInstance) -> bool:
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SshError:
            logger.exception("SSH connection failure with %s", instance.server_name)
            return False
        try:
            OpenstackRunnerManager._run_health_check(ssh_conn, instance.server_name)
        except RunnerError:
            logger.exception("Health check failure for %s", instance.server_name)
            return False
        logger.info("Health check success for %s", instance.server_name)
        return True

    @retry(tries=3, delay=60, local_logger=logger)
    @staticmethod
    def _run_health_check(ssh_conn: SshConnection, name: str):
        result: invoke.runners.Result = ssh_conn.run("ps aux", warn=True)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s", name)
            raise RunnerError(f"Unable to SSH run `ps aux` on {name}")
        if (
            RUNNER_WORKER_PROCESS not in result.stdout
            and RUNNER_LISTENER_PROCESS not in result.stdout
        ):
            logger.warning("Runner process not found on %s", name)
            raise RunnerError(f"Runner process not found on {name}")

    @retry(tries=10, delay=60, local_logger=logger)
    def _wait_runner_startup(self, instance: OpenstackInstance) -> None:
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SshError as err:
            raise RunnerCreateError(
                f"Failed to SSH connect to {instance.server_name} openstack runner"
            ) from err

        result: invoke.runners.Result = ssh_conn.run("ps aux", warn=True)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s", instance.server_name)
            raise RunnerStartError(f"Unable to SSH run `ps aux` on {instance.server_name}")
        if RUNNER_STARTUP_PROCESS not in result.stdout:
            logger.warning("Runner startup process not found on %s", instance.server_name)
            return RunnerStartError(f"Runner startup process not found on {instance.server_name}")
        logger.info("Runner startup process found to be healthy on %s", instance.server_name)

    @staticmethod
    def _generate_runner_id() -> RunnerId:
        return secrets.token_hex(12)

    @staticmethod
    def _issue_runner_installed_metric(
        name: str,
        flavor: str,
        install_start_timestamp: float,
        install_end_timestamp: float,
    ) -> None:
        try:
            metric_events.issue_event(
                event=metric_events.RunnerInstalled(
                    timestamp=install_start_timestamp,
                    flavor=flavor,
                    duration=install_end_timestamp - install_start_timestamp,
                )
            )
        except IssueMetricEventError:
            logger.exception("Failed to issue RunnerInstalled metric")

        try:
            storage = metrics_storage.create(name)
        except CreateMetricsStorageError:
            logger.exception(
                "Failed to create metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
        else:
            try:
                (storage.path / runner_metrics.RUNNER_INSTALLED_TS_FILE_NAME).write_text(
                    str(install_end_timestamp), encoding="utf-8"
                )
            except FileNotFoundError:
                logger.exception(
                    "Failed to write runner-installed.timestamp into metrics storage "
                    "for runner %s, will not be able to issue all metrics.",
                    name,
                )

    @staticmethod
    def _pull_runner_metrics(name: str, ssh_conn: SshConnection) -> None:
        try:
            storage = metrics_storage.get(name)
        except GetMetricsStorageError:
            logger.exception(
                "Failed to get shared metrics storage for runner %s, "
                "will not be able to issue all metrics.",
                name,
            )
            return

        try:
            OpenstackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "pre-job-metrics.json"),
                local_path=str(storage.path / "pre-job-metrics.json"),
                max_size=MAX_METRICS_FILE_SIZE,
            )
            OpenstackRunnerManager._ssh_pull_file(
                ssh_conn=ssh_conn,
                remote_path=str(METRICS_EXCHANGE_PATH / "post-job-metrics.json"),
                local_path=str(storage.path / "post-job-metrics.json"),
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
        ssh_conn: SshConnection, remote_path: str, local_path: str, max_size: int
    ) -> None:
        """Pull file from the runner instance.

        Args:
            ssh_conn: The SSH connection instance.
            remote_path: The file path on the runner instance.
            local_path: The local path to store the file.
            max_size: If the file is larger than this, it will not be pulled.

        Raises:
            _PullFileError: Unable to pull the file from the runner instance.
            _SSHError: Issue with SSH connection.
        """
        try:
            result = ssh_conn.run(f"stat -c %s {remote_path}", warn=True)
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise SshError(f"Unable to SSH into {ssh_conn.host}") from exc
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
            raise SshError(f"Unable to SSH into {ssh_conn.host}") from exc
        except OSError as exc:
            raise _PullFileError(f"Unable to retrieve file {remote_path}") from exc

    @staticmethod
    def _run_github_runner_removal_script(
        instance_name: str, ssh_conn: SshConnection, remove_token: str
    ) -> None:
        """Run Github runner removal script.

        Args:
            ssh_conn: The SSH connection to the runner instance.
            remove_token: The GitHub instance removal token.

        Raises:
            GithubRunnerRemoveError: Unable to remove runner from GitHub.
        """
        try:
            result = ssh_conn.run(
                f"{_CONFIG_SCRIPT_PATH} remove --token {remove_token}",
                warn=True,
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
            raise GithubRunnerRemoveError(f"Failed to remove runner {instance_name} from Github.")
        except (
            TimeoutError,
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
        ) as exc:
            raise GithubRunnerRemoveError(
                f"Failed to remove runner {instance_name} from Github."
            ) from exc
