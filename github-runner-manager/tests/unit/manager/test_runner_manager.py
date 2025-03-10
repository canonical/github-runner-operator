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
    "cloud_state,removal_called",
    [
        pytest.param(None, True, id="GitHub runner offline without cloud runner"),
        pytest.param(
            CloudRunnerState.CREATED,
            False,
            id="Github runner offline with cloud runner in BUILD state.",
        ),
        pytest.param(
            CloudRunnerState.ACTIVE, True, id="Github runner offline with ACTIVE cloud runner."
        ),
        pytest.param(
            CloudRunnerState.DELETED, True, id="Github runner offline with DELETED cloud runner."
        ),
    ],
)
def test_cleanup_removes_created_runners(
    cloud_state: CloudRunnerState | None, removal_called: bool, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: TODO.
    act: TODO
    assert: TODO
    """
    instance_id = InstanceID.build("prefix-0")
    github_runner = SelfHostedRunner(
        id=1,
        name=instance_id.name,
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
                health=HealthState.HEALTHY,
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

    stats = runner_manager.cleanup()

    if removal_called:
        github_client.delete_runners.assert_called_with([github_runner])
    else:
        github_client.delete_runners.assert_called_with([])

    assert not stats
