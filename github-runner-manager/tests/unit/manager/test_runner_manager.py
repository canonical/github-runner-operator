#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the the runner_manager."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.errors import RunnerCreateError
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerState,
    HealthState,
)
from github_runner_manager.manager.models import InstanceID, RunnerConfigData, RunnerMetadata
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.platform.platform_provider import PlatformProvider
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
            id="Non reactive Github runners with any cloud state should be DELETED.",
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

    def _get_runner_config_data(instance_id, metadata, labels):
        """Return a registration token."""
        nonlocal github_runner
        github_runner.instance_id = instance_id
        return RunnerConfigData(token="token"), github_runner

    github_provider.get_runner_config_data.side_effect = _get_runner_config_data
    cloud_runner_manager.create_runner.side_effect = RunnerCreateError("")
    github_provider.get_runners.return_value = github_runners

    _ = runner_manager.create_runners(1, RunnerMetadata(), True)
    github_provider.delete_runners.assert_called_once_with([github_runner])
