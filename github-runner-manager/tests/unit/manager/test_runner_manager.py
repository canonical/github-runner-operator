#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the the runner_manager."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.manager.models import RunnerMetadata
from github_runner_manager.manager.runner_manager import FlushMode, RunnerInstance, RunnerManager
from github_runner_manager.manager.vm_manager import CloudRunnerInstance, CloudRunnerManager
from github_runner_manager.platform.platform_provider import PlatformProvider
from github_runner_manager.types_.github import SelfHostedRunner
from tests.unit.factories.runner_instance_factory import (
    CloudRunnerInstanceFactory,
    RunnerInstanceFactory,
    SelfHostedRunnerFactory,
)
from tests.unit.fake_runner_managers import FakeCloudRunnerManager, FakeGitHubRunnerPlatform


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, expected_runners, expected_cloud_runners, flush_mode",
    [
        pytest.param(
            [SelfHostedRunnerFactory()],
            [],
            [],
            [],
            FlushMode.FLUSH_IDLE,
            id="one platform runner not in cloud is cleaned up",
        ),
        pytest.param(
            [
                (
                    idle_runner_with_cloud := SelfHostedRunnerFactory(
                        busy=False,
                        status="online",
                    )
                ),
            ],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=idle_runner_with_cloud
                )
            ],
            [],
            [],
            FlushMode.FLUSH_IDLE,
            id="one idle platform runner, matching cloud runner in cloud flushed",
        ),
        pytest.param(
            [
                (
                    busy_runner_with_cloud := SelfHostedRunnerFactory(
                        busy=True,
                        status="online",
                        deletable=False,
                    )
                ),
            ],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=busy_runner_with_cloud
                )
            ],
            [busy_runner_with_cloud],
            [runner_with_platform],
            FlushMode.FLUSH_IDLE,
            id="one busy platform runner, matching cloud runner in cloud is not flushed",
        ),
        pytest.param(
            [
                (
                    busy_runner_with_cloud := SelfHostedRunnerFactory(
                        busy=True,
                        status="online",
                        deletable=False,
                    )
                ),
            ],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=busy_runner_with_cloud
                )
            ],
            [],
            [],
            FlushMode.FLUSH_BUSY,
            id="one busy platform runner, matching cloud runner in cloud is flushed in flush busy",
        ),
    ],
)
def test_flush_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[CloudRunnerInstance],
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[CloudRunnerInstance],
    flush_mode: FlushMode,
):
    """
    arrange: Given GitHub runners and Cloud runners.
    act: Call flush in the RunnerManager instance.
    assert: Expected github runners and cloud runners are flushed.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    manager.flush_runners(flush_mode=flush_mode)

    assert list(mock_platform._runners.values()) == expected_runners
    assert list(mock_cloud._cloud_runners.values()) == expected_cloud_runners


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, expected_runners, expected_cloud_runners",
    [
        pytest.param(
            [SelfHostedRunnerFactory()], [], [], [], id="one platform runner not in cloud"
        ),
        pytest.param(
            [
                (runner_with_cloud := SelfHostedRunnerFactory()),
                SelfHostedRunnerFactory(),
            ],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            [runner_with_cloud],
            [runner_with_platform],
            id="one platform runner not in cloud, one in cloud",
        ),
        pytest.param(
            [],
            [runner_without_platform := CloudRunnerInstanceFactory()],
            [],
            [runner_without_platform],
            id="cloud runner only in cloud",
        ),
        pytest.param(
            [],
            [runner_with_platform],
            [],
            [runner_with_platform],
            id="cloud runner with platform runner only in cloud",
        ),
        pytest.param(
            [SelfHostedRunnerFactory(), SelfHostedRunnerFactory(), SelfHostedRunnerFactory()],
            [],
            [],
            [],
            id="multiple runners not in cloud, none in cloud",
        ),
        pytest.param(
            [runner_with_cloud, SelfHostedRunnerFactory()],
            [runner_with_platform, runner_without_platform := CloudRunnerInstanceFactory()],
            [runner_with_cloud],
            [runner_with_platform, runner_without_platform],
            id="some in cloud, some not in cloud",
        ),
    ],
)
def test_runner_maanger_cleanup(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[CloudRunnerInstance],
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[CloudRunnerInstance],
):
    """
    arrange: Given GitHub runners and Cloud runners.
    act: Call cleanup in the RunnerManager instance.
    assert: Expected github runners and cloud runners cleanup is run.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    manager.cleanup()

    assert list(mock_platform._runners.values()) == expected_runners
    assert list(mock_cloud._cloud_runners.values()) == expected_cloud_runners


def test_runner_manager_create_runners() -> None:
    """
    arrange: None.
    act: call runner_manager.create_runners.
    assert: The runner manager will create the runner.
    """
    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"

    platform_provider = MagicMock(spec=PlatformProvider)
    runner_context_mock = MagicMock()
    github_runner = MagicMock()
    platform_provider.get_runner_context.return_value = (runner_context_mock, github_runner)

    runner_manager = RunnerManager(
        "managername",
        platform_provider=platform_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    (instance_id,) = runner_manager.create_runners(1, RunnerMetadata(), True)

    assert instance_id
    cloud_runner_manager.create_runner.assert_called_once()


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, expected_runner_instances",
    [
        pytest.param([], [], (), id="no runners"),
        pytest.param(
            [SelfHostedRunnerFactory()], [], (), id="platform runner without cloud runner"
        ),
        pytest.param(
            [],
            [cloud_runner := CloudRunnerInstanceFactory()],
            (RunnerInstanceFactory(name=cloud_runner.name),),
            id="cloud runner without platform runner",
        ),
        pytest.param(
            [runner_with_cloud := SelfHostedRunnerFactory()],
            [
                cloud_runner := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            (RunnerInstanceFactory(name=cloud_runner.name),),
            id="platform runner with cloud runner",
        ),
    ],
)
def test_runner_manager_get_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[CloudRunnerInstance],
    expected_runner_instances: tuple[RunnerInstance],
):
    """
    arrange: Given GitHub runners and Cloud runners.
    act: when RunnerManager.get_runners is called.
    assert: expected RunnerInstances are returned.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    # Test for number of runners matching and that the runner belongs to the cloud instance
    # provided. The instance contents cannot be tested due to coupled logic in how the
    # RunnerInstance is generated - which would require business logic in the test of setting up
    # RunnerInstances from cloud runners and self hosted runners.
    result = manager.get_runners()
    assert len(result) == len(expected_runner_instances)
    runner_names = {runner.name for runner in result}
    assert all(runner.name in runner_names for runner in expected_runner_instances)


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, num_delete, expected_runners, expected_cloud_runners",
    [
        pytest.param([], [], 1, [], [], id="no runners to delete"),
        pytest.param(
            [runner_with_cloud := SelfHostedRunnerFactory()],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            0,
            [runner_with_cloud],
            [runner_with_platform],
            id="num delete runners 0",
        ),
        pytest.param(
            [runner_with_cloud],
            [runner_with_platform],
            1,
            [],
            [],
            id="delete 1 runner",
        ),
    ],
)
def test_runner_manager_deterministic_delete_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[CloudRunnerInstance],
    num_delete: int,
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[CloudRunnerInstance],
):
    """
    arrange: given initial runners (platform and cloud).
    act: when RunnerManager.delete_runners is called.
    assert: expected cloud & platform runners remain.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    manager.delete_runners(num_delete)

    assert list(mock_platform._runners.values()) == expected_runners
    assert list(mock_cloud._cloud_runners.values()) == expected_cloud_runners


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, num_delete,"
    "expected_runners_count, expected_cloud_runners_count",
    [
        pytest.param(
            [runner_with_cloud, runner_with_cloud_two := SelfHostedRunnerFactory()],
            [
                runner_with_platform,
                runner_with_platform_two := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud_two
                ),
            ],
            1,
            1,
            1,
            id="delete 1 runner out of two runners",
        ),
    ],
)
def test_runner_manager_non_deterministic_delete_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[CloudRunnerInstance],
    num_delete: int,
    expected_runners_count: int,
    expected_cloud_runners_count: int,
):
    """
    arrange: given initial runners (platform and cloud).
    act: when RunnerManager.delete_runners is called.
    assert: expected cloud & platform runners remain.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    manager.delete_runners(num_delete)

    assert len(mock_platform._runners.values()) == expected_runners_count
    assert len(mock_platform._runners.values()) == expected_cloud_runners_count
