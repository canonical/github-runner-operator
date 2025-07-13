# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from datetime import timedelta
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
from github_runner_manager.manager import runner_manager as runner_manager_module
from github_runner_manager.manager.cloud_runner_manager import CloudRunnerState
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.runner_manager import (
    IssuedMetricEventsStats,
    RunnerInstance,
    RunnerManager,
)
from github_runner_manager.manager.runner_scaler import FlushMode, RunnerInfo, RunnerScaler
from github_runner_manager.metrics.events import RunnerStart, RunnerStop
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
from tests.unit.factories.runner_instance_factory import RunnerInstanceFactory

logger = logging.getLogger(__name__)


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
        reconcile_interval=10,
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
    platform_state: PlatformRunnerState | None = None,
    cloud_state: CloudRunnerState | None = None,
    health: bool | None = None,
    old_runner: bool = False,
):
    """Set the runner state for a RunnerScaler with one runner.

    Args:
        runner_scaler: The RunnerScaler instance to modify.
        platform_state: The github state to set the runner.
        cloud_state: The cloud state to set the runner.
        health: Whether the runner is healthy.
        old_runner: A runner that has had enough time to get created.
    """
    logger.info(
        "set_one_runner_state: platform_state %s, cloud_state %s, health %s",
        platform_state,
        cloud_state,
        health,
    )
    runner_dict = runner_scaler._manager._platform.state.runners
    assert len(runner_dict) == 1, "Test arrange failed: One runner should be present"
    instance_id = list(runner_dict.keys())[0]
    if old_runner:
        runner_dict[instance_id].created_at -= timedelta(
            seconds=runner_manager_module.RUNNER_MAXIMUM_CREATION_TIME + 1
        )
    if platform_state is not None:
        runner_dict[instance_id].platform_state = platform_state
    if cloud_state is not None:
        runner_dict[instance_id].cloud_state = cloud_state
    if health is not None:
        runner_dict[instance_id].health = health
    logger.info("current runner_dict: %s.", runner_dict)


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


@pytest.mark.parametrize(
    "runners, expected_runner_info",
    [
        pytest.param(
            [],
            RunnerInfo(online=0, busy=0, offline=0, unknown=0, runners=(), busy_runners=()),
            id="No runners",
        ),
        pytest.param(
            [busy_runner := RunnerInstanceFactory(platform_state=PlatformRunnerState.BUSY)],
            RunnerInfo(
                online=1,
                busy=1,
                offline=0,
                unknown=0,
                runners=(busy_runner.name,),
                busy_runners=(busy_runner.name,),
            ),
            id="One busy runner",
        ),
        pytest.param(
            [idle_runner := RunnerInstanceFactory(platform_state=PlatformRunnerState.IDLE)],
            RunnerInfo(
                online=1,
                busy=0,
                offline=0,
                unknown=0,
                runners=(idle_runner.name,),
                busy_runners=(),
            ),
            id="One idle runner",
        ),
        pytest.param(
            [offline_runner := RunnerInstanceFactory(platform_state=PlatformRunnerState.OFFLINE)],
            RunnerInfo(
                online=0,
                busy=0,
                offline=1,
                unknown=0,
                runners=(),
                busy_runners=(),
            ),
            id="One offline runner",
        ),
        pytest.param(
            [unknown_runner := RunnerInstanceFactory(platform_state=None)],
            RunnerInfo(
                online=0,
                busy=0,
                offline=0,
                unknown=1,
                runners=(),
                busy_runners=(),
            ),
            id="One unknown runner",
        ),
        pytest.param(
            [busy_runner, idle_runner, offline_runner, unknown_runner],
            RunnerInfo(
                online=2,
                busy=1,
                offline=1,
                unknown=1,
                runners=(busy_runner.name, idle_runner.name),
                busy_runners=(busy_runner.name,),
            ),
            id="One runner of each type",
        ),
    ],
)
def test_runner_scaler_get_runner_info(
    runners: list[RunnerInstance], expected_runner_info: RunnerInfo
):
    """
    arrange: given a mock runner manager.
    act: when RunnerScaler.get_runner_info is called.
    assert the expected runner info is extracted.
    """
    runner_manager = MagicMock()
    runner_manager.get_runners.return_value = runners
    runner_scaler = RunnerScaler(
        runner_manager=runner_manager,
        reactive_process_config=None,
        user=MagicMock(),
        base_quantity=0,
        max_quantity=0,
    )

    assert runner_scaler.get_runner_info() == expected_runner_info


@pytest.mark.parametrize(
    "cleanup_metrics, flush_metrics, expected_flushed",
    [
        pytest.param({}, {}, 0, id="No changes"),
        pytest.param({RunnerStart: 1}, {}, 0, id="No runner stop metrics"),
        pytest.param({RunnerStop: 1}, {}, 1, id="Runner stop metric from cleanup"),
        pytest.param({}, {RunnerStop: 1}, 1, id="Runner stop metric from flush"),
        pytest.param(
            {RunnerStop: 1},
            {RunnerStop: 1},
            2,
            id="Runner stop metrics from cleanup and flush",
        ),
    ],
)
def test_runner_scaler_flush_extract_metrics(
    cleanup_metrics: IssuedMetricEventsStats,
    flush_metrics: IssuedMetricEventsStats,
    expected_flushed: int,
):
    """
    arrange: given a mocked runner manager with that returns the given metrics.
    act: when RunnerScaler.flush is called.
    assert: the expected number of flushed runners from metrics is returned.
    """
    runner_manager = MagicMock()
    runner_manager.cleanup.return_value = cleanup_metrics
    runner_manager.flush_runners.return_value = flush_metrics

    runner_scaler = RunnerScaler(
        runner_manager=runner_manager,
        reactive_process_config=None,
        user=MagicMock(),
        base_quantity=0,
        max_quantity=0,
    )

    assert runner_scaler.flush() == expected_flushed


@pytest.mark.parametrize(
    "flush_mode, expected_flush_mode",
    [
        pytest.param(FlushMode.FLUSH_IDLE, FlushMode.FLUSH_IDLE, id="flush_idle"),
        pytest.param(FlushMode.FLUSH_BUSY, FlushMode.FLUSH_BUSY, id="flush_busy"),
    ],
)
def test_runner_scaler_flush_mode(flush_mode: FlushMode, expected_flush_mode: FlushMode):
    """
    arrange: given a mocked runner manager.
    act: when RunnerScaler.flush is called with the given flush mode.
    assert: flush_runners is called with expected mode.
    """
    runner_manager = MagicMock()

    RunnerScaler(
        runner_manager=runner_manager,
        reactive_process_config=None,
        user=MagicMock(),
        base_quantity=0,
        max_quantity=0,
    ).flush(flush_mode=flush_mode)

    runner_manager.flush_runners.assert_called_with(flush_mode=expected_flush_mode)


@pytest.mark.parametrize(
    "runners, quantity, expected_diff",
    [
        pytest.param([], 0, 0, id="no difference"),
        pytest.param([], 1, 1, id="scale up one runner"),
        pytest.param([RunnerInstanceFactory()], 0, -1, id="scale down one runner"),
    ],
)
def test_runner_scaler__reconcile_non_reactive(
    runners: list[RunnerInstance], quantity: int, expected_diff: int
):
    """
    arrange: given a mocked runner manager.
    act: when RunnerScaler._reconcile_non_reactive is called.
    assert: expected runner diff is returned.
    """
    runner_manager = MagicMock()
    runner_manager.get_runners.return_value = runners

    result = RunnerScaler(
        runner_manager=runner_manager,
        reactive_process_config=None,
        user=MagicMock(),
        base_quantity=0,
        max_quantity=0,
    )._reconcile_non_reactive(expected_quantity=quantity)

    assert result.runner_diff == expected_diff
