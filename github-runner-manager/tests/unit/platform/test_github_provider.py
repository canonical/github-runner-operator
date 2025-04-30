#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.


"""Test for the github provider module."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.platform.github_provider import (
    GithubRunnerNotFoundError,
    GitHubRunnerPlatform,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


def _params_test_get_runner_health():
    """Parameterized data for test_get_runner_health."""
    prefix = "unit-0"
    runner_id = 3
    metadata = RunnerMetadata(platform_name="github", runner_id=str(runner_id))
    instance_id = InstanceID.build(prefix=prefix)
    # The parameterized arguments are:
    # "instance_id,metadata,self_hosted_runner,expected_online,expected_busy,expected_deletable",
    return [
        pytest.param(
            instance_id,
            metadata,
            SelfHostedRunner(
                busy=False,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.OFFLINE,
                instance_id=instance_id,
                metadata=metadata,
            ),
            False,
            False,
            False,
            id="Offline runner",
        ),
        pytest.param(
            instance_id,
            metadata,
            SelfHostedRunner(
                busy=False,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.ONLINE,
                instance_id=instance_id,
                metadata=metadata,
            ),
            True,
            False,
            False,
            id="Online runner",
        ),
        pytest.param(
            instance_id,
            metadata,
            SelfHostedRunner(
                busy=True,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.OFFLINE,
                instance_id=instance_id,
                metadata=metadata,
            ),
            False,
            True,
            False,
            id="Offline busy runner",
        ),
        pytest.param(
            instance_id,
            metadata,
            GithubRunnerNotFoundError("not found"),
            False,
            False,
            True,
            id="Runner not in GitHub",
        ),
    ]


@pytest.mark.parametrize(
    "instance_id,metadata,self_hosted_runner,expected_online,expected_busy,expected_deletable",
    _params_test_get_runner_health(),
)
def test_get_runner_health(
    monkeypatch: pytest.MonkeyPatch,
    instance_id: InstanceID,
    metadata: RunnerMetadata,
    self_hosted_runner: SelfHostedRunner,
    expected_online: bool,
    expected_busy: bool,
    expected_deletable: bool,
):
    """
    arrange: Given a GitHub self-hosted runner in GitHub (possibly missing).
    act: Call GitRunnerPlatform.get_runner_health.
    assert: The expected online, busy and deletable fields are set in the health depending
        on the GitHub runner state.
    """
    prefix = "unit-0"
    github_client_mock = MagicMock(spec=GithubClient)
    github_client_mock.get_runner.side_effect = (self_hosted_runner,)

    platform = GitHubRunnerPlatform(prefix=prefix, path="org", github_client=github_client_mock)

    runner_health = platform.get_runner_health(instance_id=instance_id, metadata=metadata)

    assert runner_health
    assert runner_health.online is expected_online
    assert runner_health.busy is expected_busy
    assert runner_health.deletable is expected_deletable
