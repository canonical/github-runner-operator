#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the the runner_manager."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.configuration.github import GitHubConfiguration, GitHubRepo
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    CloudRunnerState,
    HealthState,
)
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


@pytest.mark.parametrize(
    "cloud_state,health,reactive,removal_called",
    [
        pytest.param(None, None, reactive, True, id="Any GitHub runner offline should be deleted.")
        for reactive in (True, False)
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
        os="unknown",
        instance_id=instance_id,
    )
    cloud_instances: tuple[CloudRunnerInstance, ...] = ()
    if cloud_state:
        cloud_instances = (
            CloudRunnerInstance(
                name=instance_id.name,
                instance_id=instance_id,
                health=health,
                state=cloud_state,
            ),
        )

    cloud_runner_manager = MagicMock()
    cloud_runner_manager.get_runners.return_value = cloud_instances
    github_org = GitHubRepo(owner="owner", repo="repo")
    github_configuration = GitHubConfiguration(token="token", path=github_org)
    runner_manager = RunnerManager(
        "managername",
        github_configuration=github_configuration,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    github_client = MagicMock()
    monkeypatch.setattr(runner_manager, "_github", github_client)
    github_client.get_runners.return_value = [github_runner]
    github_client.get_removal_token.return_value = "removaltoken"

    runner_manager.cleanup()

    if removal_called:
        github_client.delete_runners.assert_called_with([github_runner])
    else:
        github_client.delete_runners.assert_called_with([])
