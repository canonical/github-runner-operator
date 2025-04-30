#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the the runner_manager."""

from unittest.mock import ANY, MagicMock

import pytest

from github_runner_manager.errors import RunnerCreateError
from github_runner_manager.manager import runner_manager as runner_manager_module
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
    HealthState,
)
from github_runner_manager.manager.models import InstanceID, RunnerContext, RunnerMetadata
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.platform.platform_provider import PlatformProvider, PlatformRunnerHealth
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


@pytest.mark.parametrize(
    "cloud_state,health,reactive,removal_called",
    [
        pytest.param(
            None, None, False, True, id="Non reactive GitHub runner offline should be deleted."
        ),
        pytest.param(
            None, None, True, False, id="Reactive GitHub runner offline should be deleted."
        ),
    ]
    + [
        pytest.param(
            cloud_state,
            health,
            False,
            True,
            id="Non reactive GitHub runners with any cloud state should be DELETED.",
        )
        for cloud_state in CloudRunnerState
        for health in HealthState
    ]
    + [
        pytest.param(
            CloudRunnerState.CREATED,
            HealthState.UNKNOWN,
            True,
            False,
            id="Reactive Github offline with CREATED state cloud should not be deleted.",
        ),
        pytest.param(
            CloudRunnerState.ACTIVE,
            HealthState.UNHEALTHY,
            True,
            True,
            id="Reactive Github offline with ACTIVE and healthy cloud should be deleted.",
        ),
        pytest.param(
            CloudRunnerState.ACTIVE,
            HealthState.HEALTHY,
            True,
            False,
            id="Reactive Github offline with ACTIVE and healthy cloud should not be deleted.",
        ),
        pytest.param(
            CloudRunnerState.ACTIVE,
            HealthState.UNHEALTHY,
            True,
            True,
            id="Reactive Github offline with ACTIVE and healthy cloud should be deleted.",
        ),
    ]
    + [
        pytest.param(
            cloud_state,
            health,
            True,
            True,
            id=f"Reactive Github runners with cloud state {cloud_state} should be DELETED.",
        )
        for cloud_state in CloudRunnerState
        for health in HealthState
        if cloud_state not in (CloudRunnerState.ACTIVE, CloudRunnerState.CREATED)
    ],
)
def test_cleanup_removes_offline_expected_runners(
    cloud_state: CloudRunnerState | None,
    health: HealthState | None,
    reactive: bool,
    removal_called: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Given a runner with offline state in GitHub.
       Also given an optional runner in the cloud provider with an state.
    act: Call cleanup in the RunnerManager instance.
    assert: If appropriate, the offline runner should be deleted.
    """
    instance_id = InstanceID.build("prefix-0", reactive)
    github_runner = SelfHostedRunner(
        id=1,
        labels=[],
        status=GitHubRunnerStatus.OFFLINE,
        busy=True,
        instance_id=instance_id,
        metadata=RunnerMetadata(platform_name="github", runner_id="1"),
    )
    cloud_instances: tuple[CloudRunnerInstance, ...] = ()
    if cloud_state:
        cloud_instances = (
            CloudRunnerInstance(
                name=instance_id.name,
                instance_id=instance_id,
                metadata=RunnerMetadata(),
                health=health,
                state=cloud_state,
            ),
        )

    cloud_runner_manager = MagicMock()
    cloud_runner_manager.get_runners.return_value = cloud_instances
    github_provider = MagicMock()
    runner_manager = RunnerManager(
        "managername",
        platform_provider=github_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    github_provider.get_runners.return_value = [github_runner]
    github_provider.get_removal_token.return_value = "removaltoken"

    runner_manager.cleanup()

    if removal_called:
        github_provider.delete_runners.assert_called_with([github_runner])
    else:
        github_provider.delete_runners.assert_called_with([])


def test_failed_runner_in_openstack_cleans_github(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Prepare a RunnerManager with a cloud manager that will fail when creating a runner.
    act: Create a Runner.
    assert: When there was a failure to create a runner in the cloud manager,
            only that github runner will be deleted in GitHub.
    """
    cloud_instances: tuple[CloudRunnerInstance, ...] = ()
    cloud_runner_manager = MagicMock()
    cloud_runner_manager.get_runners.return_value = cloud_instances
    cloud_runner_manager.name_prefix = "unit-0"
    github_provider = MagicMock(spec=PlatformProvider)

    runner_manager = RunnerManager(
        "managername",
        platform_provider=github_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    github_runner = SelfHostedRunner(
        id=1,
        labels=[],
        status=GitHubRunnerStatus.OFFLINE,
        busy=True,
        instance_id=InstanceID.build("invalid"),
        metadata=RunnerMetadata(platform_name="github", runner_id="1"),
    )
    github_runners = [
        github_runner,
        SelfHostedRunner(
            id=2,
            labels=[],
            status=GitHubRunnerStatus.OFFLINE,
            busy=True,
            instance_id=InstanceID.build("unit-0"),
            metadata=RunnerMetadata(platform_name="github", runner_id="2"),
        ),
    ]

    def _get_runner_context(instance_id, metadata, labels):
        """Return the runner context."""
        nonlocal github_runner
        github_runner.instance_id = instance_id
        return RunnerContext(shell_run_script="agent"), github_runner

    github_provider.get_runner_context.side_effect = _get_runner_context
    cloud_runner_manager.create_runner.side_effect = RunnerCreateError("")
    github_provider.get_runners.return_value = github_runners

    _ = runner_manager.create_runners(1, RunnerMetadata(), True)
    github_provider.delete_runners.assert_called_once_with([github_runner])


@pytest.mark.parametrize(
    "creation_waiting_times,runner_unhealthy,runner_healthy",
    [
        pytest.param(
            (0,),
            None,
            PlatformRunnerHealth(
                instance_id=MagicMock(),
                metadata=MagicMock(),
                online=True,
                busy=False,
                deletable=False,
            ),
            id="online runner",
        ),
        pytest.param(
            (0, 0),
            PlatformRunnerHealth(
                instance_id=MagicMock(),
                metadata=MagicMock(),
                online=False,
                busy=True,
                deletable=False,
            ),
            PlatformRunnerHealth(
                instance_id=MagicMock(),
                metadata=MagicMock(),
                online=False,
                busy=False,
                deletable=True,
            ),
            id="deletable runner",
        ),
    ],
)
def test_create_runner(
    monkeypatch: pytest.MonkeyPatch,
    creation_waiting_times: tuple[int, ...],
    runner_unhealthy: PlatformRunnerHealth | None,
    runner_healthy: PlatformRunnerHealth,
):
    """
    arrange: Given a specific pattern for creation waiting times and a list of.
        PlatformRunnerHealth objects being the last one a healthy runner.
    act: call runner_manager.create_runners.
    assert: The runner manager will create the runner and make requests to check the health
        until it gets a healthy state.
    """
    monkeypatch.setattr(
        runner_manager_module, "RUNNER_CREATION_WAITING_TIMES", creation_waiting_times
    )

    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"

    platform_provider = MagicMock(spec=PlatformProvider)
    runner_context_mock = MagicMock()
    github_runner = MagicMock()
    platform_provider.get_runner_context.return_value = (runner_context_mock, github_runner)

    platform_provider.get_runner_health.side_effect = tuple(
        runner_unhealthy for _ in range(len(creation_waiting_times) - 1)
    ) + (runner_healthy,)

    runner_manager = RunnerManager(
        "managername",
        platform_provider=platform_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    (instance_id,) = runner_manager.create_runners(1, RunnerMetadata(), True)

    assert instance_id
    cloud_runner_manager.create_runner.assert_called_once()
    # The method to get the runner health was called three times
    # until the runner was online.
    assert platform_provider.get_runner_health.call_count == len(creation_waiting_times)
    platform_provider.get_runner_health.assert_called_with(metadata=ANY, instance_id=ANY)


def test_create_runner_failed_waiting(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a specific pattern for creation waiting times and a list of.
        PlatformRunnerHealth objects where none is healthy
    act: call runner_manager.create_runners.
    assert: The runner manager will create the runner, it will check for the health state,
       but the runner will not get into healthy state and the platform api for deleting
       the runner will be called.
    """
    runner_creation_waiting_times = (0, 0)
    monkeypatch.setattr(
        runner_manager_module, "RUNNER_CREATION_WAITING_TIMES", runner_creation_waiting_times
    )

    cloud_runner_manager = MagicMock(spec=CloudRunnerManager)
    cloud_runner_manager.name_prefix = "unit-0"

    platform_provider = MagicMock(spec=PlatformProvider)
    runner_context_mock = MagicMock()
    github_runner = MagicMock()
    platform_provider.get_runner_context.return_value = (runner_context_mock, github_runner)

    health_offline = PlatformRunnerHealth(
        instance_id=MagicMock(), metadata=MagicMock(), online=False, busy=False, deletable=False
    )

    platform_provider.get_runner_health.side_effect = (
        health_offline,
        health_offline,
    )

    runner_manager = RunnerManager(
        "managername",
        platform_provider=platform_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    () = runner_manager.create_runners(1, RunnerMetadata(), True)

    # The runner was started even if it failed.
    cloud_runner_manager.create_runner.assert_called_once()
    assert platform_provider.get_runner_health.call_count == 2
    platform_provider.get_runner_health.assert_called_with(metadata=ANY, instance_id=ANY)
    platform_provider.delete_runners.assert_called_once_with([ANY])
