# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Iterable
from unittest.mock import MagicMock

import pytest
from pydantic.networks import IPv4Address

from github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    Image,
    NonReactiveCombination,
    NonReactiveConfiguration,
    ProxyConfig,
    QueueConfig,
    ReactiveConfiguration,
    RepoPolicyComplianceConfig,
    SSHDebugConnection,
    SupportServiceConfig,
    UserInfo,
)
from github_runner_manager.configuration.github import (
    GitHubConfiguration,
    GitHubOrg,
    GitHubPath,
    GitHubRepo,
)
from github_runner_manager.errors import CloudError, ReconcileError
from github_runner_manager.manager import runner_manager as runner_manager_module
from github_runner_manager.manager.cloud_runner_manager import CloudRunnerState
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.runner_manager import FlushMode, RunnerManager
from github_runner_manager.manager.runner_scaler import RunnerScaler
from github_runner_manager.metrics.events import Reconciliation
from github_runner_manager.openstack_cloud.configuration import (
    OpenStackConfiguration,
    OpenStackCredentials,
)
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManagerConfig,
)
from github_runner_manager.platform.github_provider import PlatformRunnerState
from github_runner_manager.reactive.types_ import ReactiveProcessConfig
from tests.unit.mock_runner_managers import (
    MockCloudRunnerManager,
    MockGitHubRunnerPlatform,
    SharedMockRunnerManagerState,
)


def mock_runner_manager_spawn_runners(
    create_runner_args: Iterable[RunnerManager._CreateRunnerArgs],
) -> tuple[InstanceID, ...]:
    """Mock _spawn_runners method of RunnerManager.

    The _spawn_runners method uses multi-process, which copies the object, e.g., the mocks.
    There is easy way to sync the state of the mocks object across processes. Replacing the
    _spawn_runner to remove the multi-process.pool is an easier approach.

    Args:
        create_runner_args: The arguments for the create_runner method.

    Returns:
        The instance ids of the runner spawned.
    """
    return tuple(RunnerManager._create_runner(arg) for arg in create_runner_args)


@pytest.fixture(scope="function", name="github_path")
def github_path_fixture() -> GitHubPath:
    return GitHubRepo(owner="mock_owner", repo="mock_repo")


@pytest.fixture(scope="function", name="mock_runner_managers")
def mock_runner_managers_fixture(
    github_path: GitHubPath,
) -> tuple[MockCloudRunnerManager, MockGitHubRunnerPlatform]:
    state = SharedMockRunnerManagerState()
    mock_cloud = MockCloudRunnerManager(state)
    mock_github = MockGitHubRunnerPlatform(mock_cloud.name_prefix, github_path, state)
    return (mock_cloud, mock_github)


@pytest.fixture(scope="function", name="issue_events_mock")
def issue_events_mock_fixture(monkeypatch: pytest.MonkeyPatch):
    issue_events_mock = MagicMock()
    monkeypatch.setattr(
        "github_runner_manager.manager.runner_scaler.metric_events.issue_event", issue_events_mock
    )
    return issue_events_mock


@pytest.fixture(scope="function", name="runner_manager")
def runner_manager_fixture(
    monkeypatch, mock_runner_managers, github_path: GitHubPath, issue_events_mock
) -> RunnerManager:
    mock_cloud, mock_github = mock_runner_managers
    monkeypatch.setattr(
        "github_runner_manager.manager.runner_manager.RunnerManager._spawn_runners",
        mock_runner_manager_spawn_runners,
    )
    # Patch out the metrics, as metrics has their own tests.
    monkeypatch.setattr(
        "github_runner_manager.manager.runner_manager.github_metrics.job", MagicMock()
    )
    monkeypatch.setattr(
        "github_runner_manager.manager.runner_manager.runner_metrics.issue_events", MagicMock()
    )

    runner_manager = RunnerManager(
        manager_name="mock_runners",
        platform_provider=mock_github,
        cloud_runner_manager=mock_cloud,
        labels=["label1", "label2", "arm64", "noble", "flavorlabel"],
    )
    # We do not want to wait in the unit tests for machines to be ready.
    monkeypatch.setattr(runner_manager_module, "RUNNER_CREATION_WAITING_TIMES", (0,))
    return runner_manager


@pytest.fixture(scope="function", name="application_configuration")
def application_configuration_fixture() -> ApplicationConfiguration:
    """Returns a fixture with a fully populated ApplicationConfiguration."""
    return ApplicationConfiguration(
        name="app_name",
        extra_labels=["label1", "label2"],
        github_config=GitHubConfiguration(
            token="githubtoken", path=GitHubOrg(org="canonical", group="group")
        ),
        service_config=SupportServiceConfig(
            proxy_config=ProxyConfig(
                http="http://httpproxy.example.com:3128",
                https="http://httpsproxy.example.com:3128",
                no_proxy="127.0.0.1",
            ),
            use_aproxy=False,
            dockerhub_mirror="https://docker.example.com",
            ssh_debug_connections=[
                SSHDebugConnection(
                    host=IPv4Address("10.10.10.10"),
                    port=3000,
                    rsa_fingerprint="SHA256:rsa",
                    ed25519_fingerprint="SHA256:ed25519",
                )
            ],
            repo_policy_compliance=RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
        ),
        non_reactive_configuration=NonReactiveConfiguration(
            combinations=[
                NonReactiveCombination(
                    image=Image(
                        name="image_id",
                        labels=["arm64", "noble"],
                    ),
                    flavor=Flavor(
                        name="flavor",
                        labels=["flavorlabel"],
                    ),
                    base_virtual_machines=1,
                )
            ]
        ),
        reactive_configuration=ReactiveConfiguration(
            queue=QueueConfig(
                mongodb_uri="mongodb://user:password@localhost:27017",
                queue_name="app_name",
            ),
            max_total_virtual_machines=2,
            images=[
                Image(name="image_id", labels=["arm64", "noble"]),
            ],
            flavors=[Flavor(name="flavor", labels=["flavorlabel"])],
        ),
        openstack_configuration=OpenStackConfiguration(
            vm_prefix="unit_name",
            network="network",
            credentials=OpenStackCredentials(
                auth_url="auth_url",
                project_name="project_name",
                username="username",
                password="password",
                user_domain_name="user_domain_name",
                project_domain_name="project_domain_name",
                region_name="region",
            ),
        ),
    )


@pytest.fixture(scope="function", name="runner_scaler_one_runner")
def runner_scaler_one_runner_fixture(
    runner_manager: RunnerManager, user_info: UserInfo
) -> RunnerScaler:
    runner_scaler = RunnerScaler(
        runner_manager=runner_manager,
        reactive_process_config=None,
        user=user_info,
        base_quantity=1,
        max_quantity=0,
    )
    runner_scaler.reconcile()
    assert_runner_info(runner_scaler, online=1)
    return runner_scaler


def set_one_runner_state(
    runner_scaler: RunnerScaler,
    github_state: PlatformRunnerState | None = None,
    cloud_state: CloudRunnerState | None = None,
):
    """Set the runner state for a RunnerScaler with one runner.

    Args:
        runner_scaler: The RunnerScaler instance to modify.
        github_state: The github state to set the runner.
        cloud_state: The cloud state to set the runner.
    """
    runner_dict = runner_scaler._manager._platform.state.runners
    assert len(runner_dict) == 1, "Test arrange failed: One runner should be present"
    instance_id = list(runner_dict.keys())[0]
    if github_state is not None:
        runner_dict[instance_id].github_state = github_state
    if cloud_state is not None:
        runner_dict[instance_id].cloud_state = cloud_state


def assert_runner_info(
    runner_scaler: RunnerScaler, online: int = 0, busy: int = 0, offline: int = 0, unknown: int = 0
) -> None:
    """Assert runner info contains a certain amount of runners.

    Args:
        runner_scaler: The RunnerScaler to get information from.
        online: The number of online runners to assert for.
        busy: The number of buys runners to assert for.
        offline: The number of offline runners to assert for.
        unknown: The number of unknown runners to assert for.
    """
    info = runner_scaler.get_runner_info()
    assert info.offline == offline
    assert info.online == online
    assert info.busy == busy
    assert info.unknown == unknown
    assert isinstance(info.runners, tuple)
    assert len(info.runners) == online
    assert isinstance(info.busy_runners, tuple)
    assert len(info.busy_runners) == busy


def test_build_runner_scaler(
    monkeypatch: pytest.MonkeyPatch,
    application_configuration: ApplicationConfiguration,
    user_info: UserInfo,
):
    """
    arrange: Given ApplicationConfiguration and OpenStackConfiguration.
    act: Call RunnerScaler.build
    assert: The RunnerScaler was created with the expected configuration.
    """
    runner_scaler = RunnerScaler.build(application_configuration, user_info)
    assert runner_scaler
    # A few comprobations on key data
    # Pending to refactor, too invasive.
    assert runner_scaler._manager.manager_name == "app_name"
    assert runner_scaler._manager._labels == ["label1", "label2", "arm64", "noble", "flavorlabel"]
    assert runner_scaler._manager._cloud._config == OpenStackRunnerManagerConfig(
        prefix="unit_name",
        credentials=OpenStackCredentials(
            auth_url="auth_url",
            project_name="project_name",
            username="username",
            password="password",
            user_domain_name="user_domain_name",
            project_domain_name="project_domain_name",
            region_name="region",
        ),
        server_config=OpenStackServerConfig(image="image_id", flavor="flavor", network="network"),
        service_config=SupportServiceConfig(
            proxy_config=ProxyConfig(
                http="http://httpproxy.example.com:3128",
                https="http://httpsproxy.example.com:3128",
                no_proxy="127.0.0.1",
            ),
            use_aproxy=False,
            dockerhub_mirror="https://docker.example.com",
            ssh_debug_connections=[
                SSHDebugConnection(
                    host=IPv4Address("10.10.10.10"),
                    port=3000,
                    rsa_fingerprint="SHA256:rsa",
                    ed25519_fingerprint="SHA256:ed25519",
                )
            ],
            repo_policy_compliance=RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
        ),
    )
    reactive_process_config = runner_scaler._reactive_config
    assert reactive_process_config
    assert reactive_process_config == ReactiveProcessConfig(
        queue=QueueConfig(
            mongodb_uri="mongodb://user:password@localhost:27017",
            queue_name="app_name",
        ),
        manager_name="app_name",
        github_configuration=GitHubConfiguration(
            token="githubtoken", path=GitHubOrg(org="canonical", group="group")
        ),
        cloud_runner_manager=OpenStackRunnerManagerConfig(
            prefix="unit_name",
            credentials=OpenStackCredentials(
                auth_url="auth_url",
                project_name="project_name",
                username="username",
                password="password",
                user_domain_name="user_domain_name",
                project_domain_name="project_domain_name",
                region_name="region",
            ),
            server_config=OpenStackServerConfig(
                image="image_id", flavor="flavor", network="network"
            ),
            service_config=SupportServiceConfig(
                proxy_config=ProxyConfig(
                    http="http://httpproxy.example.com:3128",
                    https="http://httpsproxy.example.com:3128",
                    no_proxy="127.0.0.1",
                ),
                use_aproxy=False,
                dockerhub_mirror="https://docker.example.com",
                ssh_debug_connections=[
                    SSHDebugConnection(
                        host=IPv4Address("10.10.10.10"),
                        port=3000,
                        rsa_fingerprint="SHA256:rsa",
                        ed25519_fingerprint="SHA256:ed25519",
                    )
                ],
                repo_policy_compliance=RepoPolicyComplianceConfig(
                    token="token",
                    url="https://compliance.example.com",
                ),
            ),
        ),
        github_token="githubtoken",
        supported_labels={"label1", "arm64", "flavorlabel", "label2", "x64", "noble"},
        labels=["label1", "label2", "arm64", "noble", "flavorlabel"],
    )


def test_get_no_runner(runner_manager: RunnerManager, user_info: UserInfo):
    """
    Arrange: A RunnerScaler with no runners.
    Act: Get runner information.
    Assert: Information should contain no runners.
    """
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=0, max_quantity=0)
    assert_runner_info(runner_scaler, online=0)


def test_flush_no_runner(runner_manager: RunnerManager, user_info: UserInfo):
    """
    Arrange: A RunnerScaler with no runners.
    Act:
        1. Flush idle runners.
        2. Flush busy runners.
    Assert:
        1. No change in number of runners. Runner info should contain no runners.
        2. No change in number of runners.
    """
    # 1.
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=0, max_quantity=0)
    diff = runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)

    # 2.
    diff = runner_scaler.flush(flush_mode=FlushMode.FLUSH_BUSY)
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)


def test_reconcile_runner_create_one(runner_manager: RunnerManager, user_info: UserInfo):
    """
    Arrange: A RunnerScaler with no runners.
    Act: Reconcile to no runners.
    Assert: No changes. Runner info should contain no runners.
    """
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=0, max_quantity=0)
    diff = runner_scaler.reconcile()
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)


def test_reconcile_runner_create_one_reactive(
    monkeypatch: pytest.MonkeyPatch, runner_manager: RunnerManager, user_info: UserInfo
):
    """
    Arrange: Prepare one RunnerScaler in reactive mode.
       Fake the reconcile function in reactive to return its input.
    Act: Call reconcile with base quantity 0 and max quantity 5.
    Assert: 5 processes should be returned in the result of the reconcile.
    """
    reactive_process_config = MagicMock()
    runner_scaler = RunnerScaler(
        runner_manager, reactive_process_config, user_info, base_quantity=0, max_quantity=5
    )

    from github_runner_manager.reactive.runner_manager import ReconcileResult

    def _fake_reactive_reconcile(
        expected_quantity: int, runner_manager, reactive_process_config, user
    ):
        """Reactive reconcile fake."""
        return ReconcileResult(processes_diff=expected_quantity, metric_stats={"event": ""})

    monkeypatch.setattr(
        "github_runner_manager.reactive.runner_manager.reconcile",
        MagicMock(side_effect=_fake_reactive_reconcile),
    )
    diff = runner_scaler.reconcile()
    assert diff == 5
    assert_runner_info(runner_scaler, online=0)


def test_reconcile_error_still_issue_metrics(
    runner_manager: RunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    issue_events_mock: MagicMock,
    user_info: UserInfo,
):
    """
    Arrange: A RunnerScaler with no runners which raises an error on reconcile.
    Act: Reconcile to one runner.
    Assert: ReconciliationEvent should be issued.
    """
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=1, max_quantity=0)
    monkeypatch.setattr(
        runner_scaler._manager, "cleanup", MagicMock(side_effect=Exception("Mock error"))
    )
    with pytest.raises(Exception):
        runner_scaler.reconcile()
    issue_events_mock.assert_called_once()
    issued_event = issue_events_mock.call_args[0][0]
    assert isinstance(issued_event, Reconciliation)


def test_reconcile_raises_reconcile_error(
    runner_manager: RunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    issue_events_mock: MagicMock,
    user_info: UserInfo,
):
    """
    Arrange: A RunnerScaler with no runners which raises a Cloud error on reconcile.
    Act: Reconcile to one runner.
    Assert: ReconcileError should be raised.
    """
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=1, max_quantity=0)
    monkeypatch.setattr(
        runner_scaler._manager, "cleanup", MagicMock(side_effect=CloudError("Mock error"))
    )
    with pytest.raises(ReconcileError) as exc:
        runner_scaler.reconcile()
    assert "Failed to reconcile runners." in str(exc.value)


def test_one_runner(runner_manager: RunnerManager, user_info: UserInfo):
    """
    Arrange: A RunnerScaler with no runners.
    Act:
        1. Reconcile to one runner.
        2. Reconcile to one runner.
        3. Flush idle runners.
        4. Reconcile to one runner.
    Assert:
        1. Runner info has one runner.
        2. No changes to number of runner.
        3. Runner info has one runner.
    """
    # 1.
    runner_scaler = RunnerScaler(runner_manager, None, user_info, base_quantity=1, max_quantity=0)
    diff = runner_scaler.reconcile()
    assert diff == 1
    assert_runner_info(runner_scaler, online=1)

    # 2.
    diff = runner_scaler.reconcile()
    assert diff == 0
    assert_runner_info(runner_scaler, online=1)

    # 3.
    runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
    assert_runner_info(runner_scaler, online=0)

    # 3.
    diff = runner_scaler.reconcile()
    assert diff == 1
    assert_runner_info(runner_scaler, online=1)


def test_flush_busy_on_idle_runner(runner_scaler_one_runner: RunnerScaler):
    """
    Arrange: A RunnerScaler with one idle runner.
    Act: Run flush busy runner.
    Assert: No runners.
    """
    runner_scaler = runner_scaler_one_runner

    runner_scaler.flush(flush_mode=FlushMode.FLUSH_BUSY)
    assert_runner_info(runner_scaler, online=0)


def test_flush_busy_on_busy_runner(
    runner_scaler_one_runner: RunnerScaler,
):
    """
    Arrange: A RunnerScaler with one busy runner.
    Act: Run flush busy runner.
    Assert: No runners.
    """
    runner_scaler = runner_scaler_one_runner
    set_one_runner_state(runner_scaler, PlatformRunnerState.BUSY)

    runner_scaler.flush(flush_mode=FlushMode.FLUSH_BUSY)
    assert_runner_info(runner_scaler, online=0)


def test_get_runner_one_busy_runner(
    runner_scaler_one_runner: RunnerScaler,
):
    """
    Arrange: A RunnerScaler with one busy runner.
    Act: Run get runners.
    Assert: One busy runner.
    """
    runner_scaler = runner_scaler_one_runner
    set_one_runner_state(runner_scaler, PlatformRunnerState.BUSY)

    assert_runner_info(runner_scaler=runner_scaler, online=1, busy=1)


def test_get_runner_offline_runner(runner_scaler_one_runner: RunnerScaler):
    """
    Arrange: A RunnerScaler with one offline runner.
    Act: Run get runners.
    Assert: One offline runner.
    """
    runner_scaler = runner_scaler_one_runner
    set_one_runner_state(runner_scaler, PlatformRunnerState.OFFLINE)

    assert_runner_info(runner_scaler=runner_scaler, offline=1)


def test_get_runner_unknown_runner(runner_scaler_one_runner: RunnerScaler):
    """
    Arrange: A RunnerScaler with one offline runner.
    Act: Run get runners.
    Assert: One offline runner.
    """
    runner_scaler = runner_scaler_one_runner
    set_one_runner_state(runner_scaler, "UNKNOWN")

    assert_runner_info(runner_scaler=runner_scaler, unknown=1)
