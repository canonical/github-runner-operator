#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from pydantic import HttpUrl

from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
)
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.manager.runner_manager import RunnerInstance
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.platform.github_provider import PlatformRunnerState
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import (
    GitHubRunnerStatus,
    JITConfig,
    RunnerApplication,
    SelfHostedRunner,
)
from tests.unit.factories.runner_instance_factory import CloudRunnerInstanceFactory

logger = logging.getLogger(__name__)

# Compressed tar file for testing.
# Python `tarfile` module works on only files.
# Hardcoding a sample tar file is simpler.
TEST_BINARY = (
    b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\xed\xd1\xb1\t\xc30\x14\x04P\xd5\x99B\x13\x04\xc9"
    b"\xb6\xacyRx\x01[\x86\x8c\x1f\x05\x12HeHaB\xe0\xbd\xe6\x8a\x7f\xc5\xc1o\xcb\xd6\xae\xed\xde"
    b"\xc2\x89R7\xcf\xd33s-\xe93_J\xc8\xd3X{\xa9\x96\xa1\xf7r\x1e\x87\x1ab:s\xd4\xdb\xbe\xb5\xdb"
    b"\x1ac\xcfe=\xee\x1d\xdf\xffT\xeb\xff\xbf\xfcz\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00_{\x00"
    b"\xc4\x07\x85\xe8\x00(\x00\x00"
)


class MockGhapiClient:
    """Mock for Ghapi client."""

    def __init__(self, token: str):
        """Initialization method for GhapiClient fake.

        Args:
            token: The client token value.
        """
        self.token = token
        self.actions = MockGhapiActions()

    def last_page(self) -> int:
        """Last page number stub.

        Returns:
            Always zero.
        """
        return 0


class MockGhapiActions:
    """Mock for actions in Ghapi client."""

    def __init__(self):
        """A placeholder method for test stub/fakes initialization."""
        hash = hashlib.sha256()
        hash.update(TEST_BINARY)
        self.test_hash = hash.hexdigest()
        self.registration_token_repo = secrets.token_hex()
        self.registration_token_org = secrets.token_hex()

    def _list_runner_applications(self):
        """A placeholder method for test fake.

        Returns:
            A fake runner applications list.
        """
        runners = []
        runners.append(
            RunnerApplication(
                os="linux",
                architecture="x64",
                download_url="https://www.example.com",
                filename="test_runner_binary",
                sha256_checksum=self.test_hash,
            )
        )
        return runners

    def list_runner_applications_for_repo(self, owner: str, repo: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.

        Returns:
            A fake runner applications list.
        """
        return self._list_runner_applications()

    def list_runner_applications_for_org(self, org: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.

        Returns:
            A fake runner applications list.
        """
        return self._list_runner_applications()

    def create_registration_token_for_repo(self, owner: str, repo: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.

        Returns:
            Registration token stub.
        """
        return JITConfig(
            {"token": self.registration_token_repo, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def list_self_hosted_runners_for_repo(
        self, owner: str, repo: str, per_page: int, page: int = 0
    ):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.
            per_page: Placeholder for responses per page.
            page: Placeholder for response page number.

        Returns:
            Empty runners stub.
        """
        return {"runners": []}

    def list_self_hosted_runners_for_org(self, org: str, per_page: int, page: int = 0):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.
            per_page: Placeholder for responses per page.
            page: Placeholder for response page number.

        Returns:
            Empty runners stub.
        """
        return {"runners": []}

    def delete_self_hosted_runner_from_repo(self, owner: str, repo: str, runner_id: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.
            runner_id: Placeholder for runenr_id.
        """
        pass

    def delete_self_hosted_runner_from_org(self, org: str, runner_id: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for organisation.
            runner_id: Placeholder for runner id.
        """
        pass


@dataclass
class MockRunner:
    """Mock of a runner.

    Attributes:
        name: The name of the runner.
        instance_id: The instance id of the runner.
        metadata: Metadata of the server.
        cloud_state: The cloud state of the runner.
        platform_state: The github state of the runner.
        health: The health state of the runner.
        created_at: The cloud creation time of the runner.
        deletable: If the runner is deletable.
    """

    name: str
    instance_id: InstanceID
    metadata: RunnerMetadata
    cloud_state: CloudRunnerState
    platform_state: PlatformRunnerState
    health: bool
    created_at: datetime
    deletable: bool = False

    def __init__(self, instance_id: InstanceID):
        """Construct the object.

        Args:
            instance_id: InstanceID of the runner.
        """
        self.name = instance_id.name
        self.instance_id = instance_id
        self.metadata = RunnerMetadata()
        self.cloud_state = CloudRunnerState.ACTIVE
        self.platform_state = PlatformRunnerState.IDLE
        self.health = True
        # By default a runner that has just being created.
        self.created_at = datetime.now(timezone.utc)

    def to_cloud_runner(self) -> CloudRunnerInstance:
        """Construct CloudRunnerInstance from this object.

        Returns:
            The CloudRunnerInstance instance.
        """
        return CloudRunnerInstance(
            name=self.name,
            metadata=self.metadata,
            instance_id=self.instance_id,
            health=self.health,
            state=self.cloud_state,
            created_at=self.created_at,
        )


@dataclass
class SharedMockRunnerManagerState:
    """State shared by mock runner managers.

    For sharing the mock runner states between MockCloudRunnerManager and MockGitHubRunnerPlatform.

    Attributes:
        runners: The runners.
    """

    runners: dict[InstanceID, MockRunner]

    def __init__(self):
        """Construct the object."""
        self.runners = {}


class MockCloudRunnerManager(CloudRunnerManager):
    """Mock of CloudRunnerManager.

    Metrics is not supported in this mock.

    Attributes:
        name_prefix: The naming prefix for runners managed.
    """

    @property
    def name_prefix(self) -> str:
        """The naming prefix for runners managed."""
        return "mock_cloud_runner_manager"

    def __init__(self, initial_cloud_runners: list[CloudRunnerInstance]) -> None:
        """Initialize the Cloud Runner Manager.

        Args:
            initial_cloud_runners: A list of initial Cloud Runner Instances.
        """
        self._cloud_runners = {runner.instance_id: runner for runner in initial_cloud_runners}

    def create_runner(
        self, runner_identity: RunnerIdentity, runner_context: RunnerContext
    ) -> CloudRunnerInstance:
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

    def get_runners(self) -> Sequence[CloudRunnerInstance]:
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

        The mock runner manager does not implement this.

        Args:
            instance_ids: A list of instance ids to extract metrics from.

        Returns:
            A list of metrics extracted from VMs with given instance ids.
        """
        return []

    def cleanup(self) -> None:
        """Cleanup cloud resources.

        The mock runner manager does not implement this.
        """
        pass


class MockGitHubRunnerPlatform(PlatformProvider):
    """Mock GitHub platform provider."""

    def __init__(self, initial_runners: Sequence[SelfHostedRunner]) -> None:
        """Initialize the mock platform.

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

    def delete_runners(self, runner_ids: list[str], platform: str = "github") -> list[str]:
        """Delete runners from platform.

        Args:
            runner_ids: The runner IDs to delete.
            platform: The target platform.

        Returns:
            The successfully deleted runners.
        """
        deleted_runner_ids: list[str] = []
        runner_id_map = {str(runner.id): runner for runner in self._runners.values()}
        for runner_id in runner_ids:
            runner = runner_id_map.get(runner_id, None)
            if not runner:
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


class MockRunnerManager:
    """Mock Runner manager for testing."""

    def __init__(self, runners: Sequence[RunnerInstance]) -> None:
        """Initialize the mock runner manager.

        Args:
            runners: The runners to initialize the RunnerManager with.
        """
        self._runners = runners
