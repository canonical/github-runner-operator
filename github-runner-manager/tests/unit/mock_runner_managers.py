#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import hashlib
import logging
import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence
from unittest.mock import MagicMock

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubPath
from github_runner_manager.github_client import GithubClient
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
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.platform.github_provider import (
    PlatformRunnerState,
)
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
        prefix: The naming prefix for runners managed.
        state: The shared state between mocks runner managers.
    """

    def __init__(self, state: SharedMockRunnerManagerState):
        """Construct the object.

        Args:
            state: The shared state between cloud and github runner managers.
        """
        self.prefix = f"mock_{secrets.token_hex(4)}"
        self.state = state

    @property
    def name_prefix(self) -> str:
        """Get the name prefix of the self-hosted runners."""
        return self.prefix

    def create_runner(
        self,
        runner_identity: RunnerIdentity,
        runner_context: RunnerContext,
    ) -> None:
        """Create a self-hosted runner.

        Args:
            runner_identity: Identity of the runner to create.
            runner_context: Context for the runner.

        Returns:
            The CloudRunnerInstance for the runner
        """
        runner = MockRunner(runner_identity.instance_id)
        self.state.runners[runner_identity.instance_id] = runner
        return runner.to_cloud_runner()

    def get_runners(self) -> Sequence[CloudRunnerInstance]:
        """Get cloud self-hosted runners.

        Returns:
            Information on the runner instances.
        """
        return [runner.to_cloud_runner() for runner in self.state.runners.values()]

    def delete_runner(self, instance_id: InstanceID) -> RunnerMetrics | None:
        """Delete self-hosted runner.

        Args:
            instance_id: The instance id of the runner to delete.

        Returns:
            Any runner metrics produced during deletion.
        """
        runner = self.state.runners.pop(instance_id, None)
        if runner is not None:
            return MagicMock()
        return []

    def cleanup(self) -> None:
        """Cleanup runner dangling resources on the cloud."""


class MockGitHubRunnerPlatform(PlatformProvider):
    """Mock of GitHubRunnerPlatform.

    Attributes:
        github: The GitHub client.
        name_prefix: The naming prefix for runner managed.
        state: The shared state between mock runner managers.
        path: The GitHub path to register the runners under.
    """

    def __init__(self, name_prefix: str, path: GitHubPath, state: SharedMockRunnerManagerState):
        """Construct the object.

        Args:
            name_prefix: The naming prefix for runner managed.
            path: The GitHub path to register the runners under.
            state: The shared state between mock runner managers.
        """
        self.github = GithubClient("mock_token")
        self.github._client = MockGhapiClient("mock_token")
        self.name_prefix = name_prefix
        self.state = state
        self.path = path

    def get_runner_health(
        self,
        runner_identity: RunnerIdentity,
    ) -> PlatformRunnerHealth:
        """Get info on self-hosted runner.

        Args:
            runner_identity: Identity of the runner.

        Returns:
            Information about the health of the runner
        """
        if runner_identity.instance_id in self.state.runners:
            runner = self.state.runners[runner_identity.instance_id]
            return PlatformRunnerHealth(
                identity=runner_identity,
                online=runner.platform_state != PlatformRunnerState.OFFLINE,
                busy=runner.platform_state == PlatformRunnerState.BUSY,
                deletable=runner.deletable,
            )
        return PlatformRunnerHealth(
            identity=runner_identity,
            online=False,
            busy=False,
            deletable=True,
        )

    def get_runners_health(
        self, requested_runners: list[RunnerIdentity]
    ) -> "list[PlatformRunnerHealth]":
        """Get information from the requested runners health.

        Args:
            requested_runners: List of runners to get health information for.

        Returns:
            Health information for the runners.
        """
        found_identities = []
        for identity in requested_runners:
            if identity.instance_id in self.state.runners:
                runner = self.state.runners[identity.instance_id]
                if runner.health:
                    found_identities.append(identity)
        requested_runners = [self.get_runner_health(identity) for identity in found_identities]
        return RunnersHealthResponse(requested_runners=requested_runners)

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: str, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get the registration JIT token for registering runners on GitHub.

        Args:
            metadata: Metadata of the server.
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token and the SelfHostedRunner
        """
        runner = MagicMock(spec=list(SelfHostedRunner.__fields__.keys()))
        runner.id = 5
        return RunnerContext(shell_run_script="fake-agent"), runner

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get the runners.

        Args:
            states: The states to filter for.

        Returns:
            List of runners.
        """
        if states is None:
            states = [member.value for member in PlatformRunnerState]

        platform_state_set = set(states)
        runner_id = random.randint(1, 1000000)
        return tuple(
            SelfHostedRunner(
                busy=runner.platform_state == PlatformRunnerState.BUSY,
                id=runner_id,
                labels=[],
                instance_id=InstanceID.build_from_name(self.name_prefix, runner.name),
                status=(
                    GitHubRunnerStatus.OFFLINE
                    if runner.platform_state == PlatformRunnerState.OFFLINE
                    else GitHubRunnerStatus.ONLINE
                ),
                metadata=RunnerMetadata(platform_name="github", runner_id=str(runner_id)),
            )
            for runner in self.state.runners.values()
            if runner.platform_state in platform_state_set
        )

    def delete_runner(self, runner_identity: RunnerIdentity) -> None:
        """Delete a runner.

        Args:
            runner_identity: Runner to delete.
        """
        if runner_identity.instance_id in self.state.runners:
            del self.state.runners[runner_identity.instance_id]

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            metadata: Metadata of the instance.
            job_url: The URL of the job.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get the Job info from the provider.

        Args:
            metadata: Metadata of the runner.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError
