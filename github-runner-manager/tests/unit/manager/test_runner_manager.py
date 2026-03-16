#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the the runner_manager."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.errors import RunnerCreateError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.models import RunnerMetadata
from github_runner_manager.manager.runner_manager import (
    CreateRunnersResult,
    FlushMode,
    RunnerInstance,
    RunnerManager,
)
from github_runner_manager.manager.vm_manager import VM, CloudRunnerManager
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
            [SelfHostedRunnerFactory(busy=False)],
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
            # GitHub returns 422 unprocessible entity on busy runners. The deletion of VM should
            # trigger it to be deleted on next reconcile as a runner without VM pair.
            [busy_runner_with_cloud],
            [],
            FlushMode.FLUSH_BUSY,
            id="one busy platform runner, matching cloud runner in cloud is flushed in flush busy",
        ),
    ],
)
def test_flush_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[VM],
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[VM],
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
            [SelfHostedRunnerFactory(busy=False)],
            [],
            [],
            [],
            id="one platform runner not in cloud",
        ),
        pytest.param(
            [
                (runner_with_cloud := SelfHostedRunnerFactory()),
                SelfHostedRunnerFactory(busy=False),
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
            [
                SelfHostedRunnerFactory(online=False, busy=False, deletable=True),
                SelfHostedRunnerFactory(online=False, busy=False, deletable=True),
                SelfHostedRunnerFactory(online=False, busy=False, deletable=True),
            ],
            [],
            [],
            [],
            id="multiple runners not in cloud, none in cloud",
        ),
        pytest.param(
            [runner_with_cloud, SelfHostedRunnerFactory(online=False, busy=False, deletable=True)],
            [runner_with_platform, runner_without_platform := CloudRunnerInstanceFactory()],
            [runner_with_cloud],
            [runner_with_platform, runner_without_platform],
            id="some in cloud, some not in cloud",
        ),
    ],
)
def test_runner_manager_cleanup(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[VM],
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[VM],
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


def test_create_runners_with_outcome_marks_cloud_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: A runner manager whose single create attempt raises RunnerCreateError.
    act: Call create_runners_with_outcome.
    assert: The result marks a cloud create failure and no IDs are returned.
    """
    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"
    runner_manager = RunnerManager(
        "managername",
        platform_provider=MagicMock(spec=PlatformProvider),
        cloud_runner_manager=cloud_runner_manager,
        labels=[],
    )

    def _raise_cloud_failure(_args):
        raise RunnerCreateError("quota exceeded")

    monkeypatch.setattr(RunnerManager, "_create_runner", staticmethod(_raise_cloud_failure))

    result = runner_manager.create_runners_with_outcome(1, RunnerMetadata(), True)

    assert result == CreateRunnersResult(created_ids=tuple(), had_cloud_create_failure=True)


def test_create_runners_with_outcome_aggregates_batched_cloud_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: A runner manager whose batched create path returns one success and one cloud failure.
    act: Call create_runners_with_outcome for two runners.
    assert: The result preserves successful IDs and reports the cloud failure.
    """
    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"
    runner_manager = RunnerManager(
        "managername",
        platform_provider=MagicMock(spec=PlatformProvider),
        cloud_runner_manager=cloud_runner_manager,
        labels=[],
    )
    expected_instance = InstanceID.build("unit-0")
    monkeypatch.setattr(
        RunnerManager,
        "_spawn_runners_using_multiprocessing",
        staticmethod(
            lambda create_runner_args_sequence, num: CreateRunnersResult(  # noqa: ARG005
                created_ids=(expected_instance,), had_cloud_create_failure=True
            )
        ),
    )

    result = runner_manager.create_runners_with_outcome(2, RunnerMetadata(), True)

    assert result == CreateRunnersResult(
        created_ids=(expected_instance,), had_cloud_create_failure=True
    )


def test_create_runners_returns_created_ids_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: A runner manager whose detailed create result includes a cloud failure flag.
    act: Call create_runners.
    assert: The legacy API still returns only the created IDs.
    """
    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"
    runner_manager = RunnerManager(
        "managername",
        platform_provider=MagicMock(spec=PlatformProvider),
        cloud_runner_manager=cloud_runner_manager,
        labels=[],
    )
    expected_instance = InstanceID.build("unit-0")

    monkeypatch.setattr(
        runner_manager,
        "create_runners_with_outcome",
        lambda num, metadata, reactive=False: CreateRunnersResult(  # noqa: ARG005
            created_ids=(expected_instance,), had_cloud_create_failure=True
        ),
    )

    assert runner_manager.create_runners(1, RunnerMetadata(), True) == (expected_instance,)


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
            (RunnerInstanceFactory(name=cloud_runner.instance_id.name),),
            id="cloud runner without platform runner",
        ),
        pytest.param(
            [runner_with_cloud := SelfHostedRunnerFactory()],
            [
                cloud_runner := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            (RunnerInstanceFactory(name=cloud_runner.instance_id.name),),
            id="platform runner with cloud runner",
        ),
    ],
)
def test_runner_manager_get_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[VM],
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
            [runner_with_cloud := SelfHostedRunnerFactory(busy=True)],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            0,
            [runner_with_cloud],
            [runner_with_platform],
            id="num delete runners 0 (busy runner not deleted)",
        ),
        pytest.param(
            [runner_with_cloud := SelfHostedRunnerFactory(busy=True)],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            1,
            # the runner remains on GitHub platform until next reconcile since GitHub cannot
            # delete busy runners
            [runner_with_cloud],
            [],
            id="num delete runners 1 (busy runner force deleted)",
        ),
        pytest.param(
            [
                runner_with_cloud := SelfHostedRunnerFactory(
                    online=True, busy=False, deletable=False
                )
            ],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            0,
            [runner_with_cloud],
            [runner_with_platform],
            id="num delete runners 0 (idle runner not deleted)",
        ),
        pytest.param(
            [runner_with_cloud := SelfHostedRunnerFactory(busy=False)],
            [
                runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=runner_with_cloud
                )
            ],
            1,
            [],
            [],
            id="num delete runners 1 (idle runner deleted)",
        ),
        pytest.param(
            [
                idle_runner_with_cloud := SelfHostedRunnerFactory(busy=False),
                busy_runner_with_cloud := SelfHostedRunnerFactory(busy=True),
            ],
            [
                idle_runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=idle_runner_with_cloud
                ),
                busy_runner_with_platform := CloudRunnerInstanceFactory.from_self_hosted_runner(
                    self_hosted_runner=busy_runner_with_cloud
                ),
            ],
            1,
            [busy_runner_with_cloud],
            [busy_runner_with_platform],
            id="num delete runners 1 (idle runner prioritized for deletion)",
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
    initial_cloud_runners: list[VM],
    num_delete: int,
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[VM],
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
    initial_cloud_runners: list[VM],
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


@pytest.mark.parametrize(
    "initial_runners, initial_cloud_runners, num_delete,"
    "expected_deleted, expected_runners, expected_cloud_runners",
    [
        pytest.param(
            [
                idle_runner := SelfHostedRunnerFactory(busy=False),
                busy_runner := SelfHostedRunnerFactory(busy=True, deletable=False),
            ],
            [
                CloudRunnerInstanceFactory.from_self_hosted_runner(idle_runner),
                busy_vm := CloudRunnerInstanceFactory.from_self_hosted_runner(busy_runner),
            ],
            2,
            1,
            [busy_runner],
            [busy_vm],
            id="idle runner deleted, busy runner and VM preserved",
        ),
        pytest.param(
            [busy_runner := SelfHostedRunnerFactory(busy=True, deletable=False)],
            [busy_vm := CloudRunnerInstanceFactory.from_self_hosted_runner(busy_runner)],
            1,
            0,
            [busy_runner],
            [busy_vm],
            id="only busy runners, nothing deleted",
        ),
    ],
)
def test_soft_delete_runners(
    initial_runners: list[SelfHostedRunner],
    initial_cloud_runners: list[VM],
    num_delete: int,
    expected_deleted: int,
    expected_runners: list[SelfHostedRunner],
    expected_cloud_runners: list[VM],
):
    """
    arrange: Given initial runners (platform and cloud) with busy runners present.
    act: Call soft_delete_runners.
    assert: Busy runners and their VMs are never deleted.
    """
    mock_platform = FakeGitHubRunnerPlatform(initial_runners=initial_runners)
    mock_cloud = FakeCloudRunnerManager(initial_cloud_runners=initial_cloud_runners)
    manager = RunnerManager(
        "test-manager", platform_provider=mock_platform, cloud_runner_manager=mock_cloud, labels=[]
    )

    deleted_count = manager.soft_delete_runners(num=num_delete)

    assert deleted_count == expected_deleted
    assert list(mock_platform._runners.values()) == expected_runners
    assert list(mock_cloud._cloud_runners.values()) == expected_cloud_runners
