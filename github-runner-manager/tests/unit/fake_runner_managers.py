#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
from typing import Sequence
from unittest.mock import MagicMock

from pydantic import HttpUrl

from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.manager.vm_manager import VM, CloudRunnerManager
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.openstack_cloud.openstack_cloud import _MAX_NOVA_COMPUTE_API_VERSION
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner
from tests.unit.factories.runner_instance_factory import CloudRunnerInstanceFactory

logger = logging.getLogger(__name__)


class FakeOpenstackCloud:
    """Fake implementation of OpenstackCloud."""

    _MOCK_COMPUTE_ENDPOINT = "mock-compute-endpoint"
    _MOCK_COMPUTE_ENDPOINT_RESPONSE = {"version": {"version": _MAX_NOVA_COMPUTE_API_VERSION}}

    def __init__(
        self,
        initial_servers: list[InstanceID],
        server_to_errors: dict[InstanceID, Exception] | None = None,
    ) -> None:
        """Initialize the OpenstackCloud mock object."""
        self.servers = {instance.name: instance for instance in initial_servers}
        self._injected_errors = {
            instance.name: exc for instance, exc in (server_to_errors or {}).items()
        }
        # Create a consistent mock response for session.get calls
        self._session_response_mock = MagicMock()
        self._session_response_mock.json.return_value = self._MOCK_COMPUTE_ENDPOINT_RESPONSE

    def __enter__(self) -> "FakeOpenstackCloud":
        """Fake enter method for context entering."""
        return self

    def __exit__(self, *args, **kwargs) -> None:
        """Fake exit method for context exiting."""
        return

    def connect(self) -> "FakeOpenstackCloud":
        """Fake OpenStack lib's connect function."""
        return self

    @property
    def compute(self) -> "FakeOpenstackCloud":
        """Fake the compute API attribute."""
        return self

    def get_endpoint(self) -> str:
        """Fake endpoint string for compute endpoint."""
        return self._MOCK_COMPUTE_ENDPOINT

    @property
    def session(self) -> "FakeOpenstackCloud":
        """Fake the connection session attribute."""
        return self

    def get(self, url: str, timeout: int | None = None) -> MagicMock:
        """Fake the session.get method.

        Args:
            url: The URL to get.
            timeout: The timeout for the request (ignored in mock).

        Returns:
            A mock response object.
        """
        return self._session_response_mock

    def delete_server(
        self,
        name_or_id: str,
        wait: bool = False,
        timeout: int = 180,
        delete_ips: bool = False,
        delete_ip_retry: int = 1,
    ) -> bool:
        """Fake method for deleting server."""
        injected_test_error = self._injected_errors.pop(name_or_id, None)
        if injected_test_error:
            raise injected_test_error

        if self.servers.pop(name_or_id, None):
            return True
        return False

    def delete_keypair(self, *args, **kwargs):
        """Fake delete keypair method."""
        pass


class FakeCloudRunnerManager(CloudRunnerManager):
    """Fake of CloudRunnerManager.

    Metrics is not supported in this fake.

    Attributes:
        name_prefix: The naming prefix for runners managed.
    """

    @property
    def name_prefix(self) -> str:
        """The naming prefix for runners managed."""
        return "fake_cloud_runner_manager"

    def __init__(self, initial_cloud_runners: list[VM]) -> None:
        """Initialize the Cloud Runner Manager.

        Args:
            initial_cloud_runners: A list of initial Cloud Runner Instances.
        """
        self._cloud_runners = {runner.instance_id: runner for runner in initial_cloud_runners}

    def create_runner(self, runner_identity: RunnerIdentity, runner_context: RunnerContext) -> VM:
        """Create a runner instance for the given runner identity and context.

        Args:
            runner_identity: The runner identity to create a runner for.
            runner_context: The context for the runner to create a runner for.

        Returns:
            The created runner instance.
        """
        created_runner = CloudRunnerInstanceFactory(instance_id=runner_identity.instance_id)
        self._cloud_runners[runner_identity.instance_id] = created_runner
        return created_runner

    def get_vms(self) -> Sequence[VM]:
        """Get all the cloud runner instances managed by the manager.

        Returns:
            A list of cloud runner instances.
        """
        return list(self._cloud_runners.values())

    def delete_vms(self, instance_ids: Sequence[InstanceID]) -> list[InstanceID]:
        """Delete VMs with given instance ids.

        Args:
            instance_ids: A list of instance ids to delete.

        Returns:
            A list of instance ids that were deleted.
        """
        deleted_instance_ids: list[InstanceID] = []
        for instance_id in instance_ids:
            cloud_runner = self._cloud_runners.pop(instance_id, None)
            if not cloud_runner:
                continue
            deleted_instance_ids.append(cloud_runner.instance_id)
        return deleted_instance_ids

    def extract_metrics(self, instance_ids: Sequence[InstanceID]) -> list[RunnerMetrics]:
        """Extract metrics from VMs with given instance ids.

        The fake runner manager does not implement this.

        Args:
            instance_ids: A list of instance ids to extract metrics from.

        Returns:
            A list of metrics extracted from VMs with given instance ids.
        """
        return []

    def cleanup(self) -> None:
        """Cleanup cloud resources.

        The fake runner manager does not implement this.
        """
        pass


class FakeGitHubRunnerPlatform(PlatformProvider):
    """Fake GitHub platform provider."""

    def __init__(self, initial_runners: Sequence[SelfHostedRunner]) -> None:
        """Initialize the fake platform.

        Args:
            initial_runners: Runners to instantiate the platform with.
        """
        self._runners = {runner.identity.instance_id: runner for runner in initial_runners}

    def get_runner_health(self, runner_identity: RunnerIdentity) -> PlatformRunnerHealth:
        """Get runner health of a runner with given runner identity.

        Args:
            runner_identity: The identity of the runner to query health status.

        Returns:
            The PlatformRunnerHealth status of the runner.
        """
        runner = self._runners.get(runner_identity.instance_id, None)
        if not runner:
            return PlatformRunnerHealth(
                identity=runner_identity,
                online=False,
                busy=False,
                deletable=True,
                runner_in_platform=False,
            )
        return PlatformRunnerHealth(
            identity=runner_identity,
            online=runner.status == GitHubRunnerStatus.ONLINE,
            busy=runner.busy,
            deletable=False,
        )

    def get_runners_health(self, requested_runners: list[RunnerIdentity]) -> RunnersHealthResponse:
        """Batch get runners health.

        Args:
            requested_runners: The runners to get. the health information for.

        Returns:
            The requested runners health info.
        """
        response = RunnersHealthResponse()

        for requested_runner in requested_runners:
            runner = self._runners.get(requested_runner.instance_id, None)
            if runner:
                response.requested_runners.append(
                    self.get_runner_health(runner_identity=runner.identity)
                )
                continue
            response.failed_requested_runners.append(requested_runner)

        requested_runner_ids = set(runner.instance_id for runner in requested_runners)
        for instance_id, runner in self._runners.items():
            if instance_id in requested_runner_ids:
                continue
            response.non_requested_runners.append(runner.identity)
        return response

    def delete_runners(self, runner_ids: list[str]) -> list[str]:
        """Delete runners from platform.

        Args:
            runner_ids: The runner IDs to delete.

        Returns:
            The successfully deleted runners.
        """
        deleted_runner_ids: list[str] = []
        runner_id_map = {str(runner.id): runner for runner in self._runners.values()}
        for runner_id in runner_ids:
            runner = runner_id_map.get(runner_id, None)
            if not runner:
                continue
            # GitHub will issue 422 Unprocessible entity on trying to delete busy runners.
            if runner.busy:
                continue
            self._runners.pop(runner.identity.instance_id)
            deleted_runner_ids.append(runner_id)
        return deleted_runner_ids

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get a context for a runner.

        Args:
            metadata: The runner's metadata.
            instance_id: The ID of the instance.
            labels: The labels of the instance.

        Raises:
            NotImplementedError: This method is not tested with this mock.
        """
        raise NotImplementedError

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if a job has been picked up by the runner.

        Args:
            metadata: The metadata of the runner.
            job_url: The URL of the job.

        Raises:
            NotImplementedError: This method is not tested with this mock.
        """
        raise NotImplementedError

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get information about a job.

        Args:
            metadata: The metadata of the runner.
            repository: The name of the repository.
            workflow_run_id: The ID of the workflow run.
            runner: The ID of the runner.

        Raises:
            NotImplementedError: This method is not tested with this mock.
        """
        raise NotImplementedError
