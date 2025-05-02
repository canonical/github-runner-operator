# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for self-hosted runner on OpenStack."""

import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import jinja2

from github_runner_manager.configuration import UserInfo
from github_runner_manager.errors import (
    MissingServerConfigError,
    OpenStackError,
    RunnerCreateError,
    SSHError,
)
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
)
from github_runner_manager.manager.models import InstanceID, RunnerContext, RunnerMetadata
from github_runner_manager.manager.runner_manager import HealthState
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.openstack_cloud.constants import (
    CREATE_SERVER_TIMEOUT,
    METRICS_EXCHANGE_PATH,
)
from github_runner_manager.openstack_cloud.models import OpenStackRunnerManagerConfig
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud, OpenstackInstance
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient
from github_runner_manager.utilities import set_env_var

logger = logging.getLogger(__name__)

_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"

RUNNER_STARTUP_PROCESS = "/home/ubuntu/actions-runner/run.sh"

OUTDATED_METRICS_STORAGE_IN_SECONDS = CREATE_SERVER_TIMEOUT + 30  # add a bit on top of the timeout


class _GithubRunnerRemoveError(Exception):
    """Represents an error while SSH into a runner and running the remove script."""


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
        user: UserInfo,
    ) -> None:
        """Construct the object.

        Args:
            config: The configuration for the openstack runner manager.
            user: The
        """
        self._config = config
        self._credentials = config.credentials
        self._openstack_cloud = OpenstackCloud(
            credentials=self._credentials,
            prefix=self.name_prefix,
            system_user=user.user,
            proxy_command=config.service_config.manager_proxy_command,
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

    def create_runner(
        self,
        instance_id: InstanceID,
        metadata: RunnerMetadata,
        runner_context: RunnerContext,
    ) -> CloudRunnerInstance:
        """Create a self-hosted runner.

        Args:
            instance_id: Instance ID for the runner to create.
            metadata: Metadata for the runner.
            runner_context: Context data for spawning the runner.

        Raises:
            MissingServerConfigError: Unable to create runner due to missing configuration.
            RunnerCreateError: Unable to create runner due to OpenStack issues.

        Returns:
            The newly created runner instance.
        """
        if (server_config := self._config.server_config) is None:
            raise MissingServerConfigError("Missing server configuration to create runners")

        cloud_init = self._generate_cloud_init(runner_context=runner_context)
        try:
            instance = self._openstack_cloud.launch_instance(
                metadata=metadata,
                instance_id=instance_id,
                server_config=server_config,
                cloud_init=cloud_init,
                ingress_tcp_ports=runner_context.ingress_tcp_ports,
            )
        except OpenStackError as err:
            raise RunnerCreateError(f"Failed to create {instance_id} openstack runner") from err

        logger.info("Runner %s created successfully", instance.instance_id)
        return self._build_cloud_runner_instance(instance)

    def get_runners(self) -> Sequence[CloudRunnerInstance]:
        """Get cloud self-hosted runners.

        Returns:
            Information on the runner instances.
        """
        instances = self._openstack_cloud.get_instances()
        return [self._build_cloud_runner_instance(instance) for instance in instances]

    def _build_cloud_runner_instance(
        self, instance: OpenstackInstance, healthy: bool | None = None
    ) -> CloudRunnerInstance:
        """Build a new cloud runner instance from an openstack instance."""
        metadata = instance.metadata
        return CloudRunnerInstance(
            name=instance.instance_id.name,
            metadata=metadata,
            instance_id=instance.instance_id,
            health=HealthState.from_value(healthy),
            state=CloudRunnerState.from_openstack_server_status(instance.status),
            created_at=instance.created_at,
        )

    def delete_runner(self, instance_id: InstanceID) -> runner_metrics.RunnerMetrics | None:
        """Delete self-hosted runners.

        Args:
            instance_id: The instance id of the runner to delete.

        Returns:
            Any metrics collected during the deletion of the runner.
        """
        logger.debug("Delete instance %s", instance_id)
        instance = self._openstack_cloud.get_instance(instance_id)
        if instance is None:
            logger.warning(
                "Unable to delete instance %s as it is not found",
                instance_id,
            )
            return None

        pulled_metrics = self._delete_runner(instance)
        logger.debug(
            "Metrics extracted, deleting instance %s %s", instance_id, instance.instance_id
        )
        logger.debug("Instance deleted successfully %s %s", instance_id, instance.instance_id)
        logger.debug("Extract metrics for runner %s %s", instance_id, instance.instance_id)
        cloud_instance = self._build_cloud_runner_instance(instance)
        return pulled_metrics.to_runner_metrics(cloud_instance, instance.created_at)

    def _delete_runner(self, instance: OpenstackInstance) -> runner_metrics.PulledMetrics:
        """Delete self-hosted runners by openstack instance.

        Args:
            instance: The OpenStack instance.
        """
        pulled_metrics = runner_metrics.PulledMetrics()
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
            pulled_metrics = runner_metrics.pull_runner_metrics(instance.instance_id, ssh_conn)
        except SSHError:
            logger.exception(
                "Failed to get SSH connection while removing %s", instance.instance_id
            )
            logger.warning(
                "Skipping runner remove script for %s due to SSH issues", instance.instance_id
            )

        try:
            self._openstack_cloud.delete_instance(instance.instance_id)
        except OpenStackError:
            logger.exception(
                "Unable to delete openstack instance for runner %s", instance.instance_id
            )
        return pulled_metrics

    def _generate_cloud_init(self, runner_context: RunnerContext) -> str:
        """Generate cloud init userdata.

        This is the script the openstack server runs on startup.

        Args:
            runner_context: Context for the runner.

        Returns:
            The cloud init userdata for openstack instance.
        """
        # We do not autoscape, the reason is that we are not generating html or xml
        jinja = jinja2.Environment(  # nosec
            loader=jinja2.PackageLoader("github_runner_manager", "templates")
        )

        service_config = self._config.service_config
        runner_http_proxy = (
            service_config.runner_proxy_config.proxy_address
            if service_config.runner_proxy_config
            else None
        )
        ssh_debug_info = (
            secrets.choice(service_config.ssh_debug_connections)
            if service_config.ssh_debug_connections
            else None
        )
        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(PRE_JOB_SCRIPT),
            dockerhub_mirror=service_config.dockerhub_mirror or "",
            ssh_debug_info=ssh_debug_info,
            tmate_server_proxy=runner_http_proxy,
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

        aproxy_address = (
            service_config.runner_proxy_config.proxy_address if service_config.use_aproxy else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            run_script=runner_context.shell_run_script,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=service_config.dockerhub_mirror,
            ssh_debug_info=ssh_debug_info,
            runner_proxy_config=service_config.runner_proxy_config,
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
