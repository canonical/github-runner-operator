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
)
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.platform.platform_provider import (
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


def test_cleanup_removes_runners_in_platform_not_in_cloud(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a runner in GitHub that is not in the cloud provider.
    act: Call cleanup in the RunnerManager instance.
    assert: The github runner should be deleted.
    """
    instance_id = InstanceID.build("prefix-0")
    github_runner_identity = RunnerIdentity(
        instance_id=instance_id, metadata=RunnerMetadata(platform_name="github", runner_id="1")
    )

    cloud_runner_manager = MagicMock()
    cloud_runner_manager.get_runners.return_value = []
    github_provider = MagicMock()
    runner_manager = RunnerManager(
        "managername",
        platform_provider=github_provider,
        cloud_runner_manager=cloud_runner_manager,
        labels=["label1", "label2"],
    )

    github_provider.get_runners_health.return_value = RunnersHealthResponse(
        non_requested_runners=[github_runner_identity]
    )

    runner_manager.cleanup()

    github_provider.delete_runner.assert_called_with(github_runner_identity)
    cloud_runner_manager.delete_runner.assert_not_called()


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

    identity = RunnerIdentity(
        instance_id=InstanceID.build("invalid"),
        metadata=RunnerMetadata(platform_name="github", runner_id="1"),
    )
    github_runner = SelfHostedRunner(
        identity=identity,
        id=1,
        labels=[],
        status=GitHubRunnerStatus.OFFLINE,
        busy=True,
    )

    def _get_runner_context(instance_id, metadata, labels):
        """Return the runner context."""
        nonlocal github_runner
        github_runner.identity.instance_id = instance_id
        return RunnerContext(shell_run_script="agent"), github_runner

    github_provider.get_runner_context.side_effect = _get_runner_context
    cloud_runner_manager.create_runner.side_effect = RunnerCreateError("")

    _ = runner_manager.create_runners(1, RunnerMetadata(), True)
    github_provider.delete_runner.assert_called_once_with(github_runner.identity)


def test_create_runner() -> None:
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
