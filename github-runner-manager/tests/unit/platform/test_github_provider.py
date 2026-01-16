#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.


"""Test for the github provider module."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.platform.github_provider import (
    GithubRunnerNotFoundError,
    GitHubRunnerPlatform,
)
from github_runner_manager.platform.platform_provider import (
    DeleteRunnerBusyError,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner


def _params_test_get_runner_health():
    """Parameterized data for test_get_runner_health."""
    prefix = "unit-0"
    runner_id = 3
    metadata = RunnerMetadata(platform_name="github", runner_id=str(runner_id))
    instance_id = InstanceID.build(prefix=prefix)
    identity = RunnerIdentity(instance_id=instance_id, metadata=metadata)
    # The parameterized arguments are:
    # "instance_id,metadata,self_hosted_runner,expected_online,expected_busy,expected_deletable",
    return [
        pytest.param(
            instance_id,
            metadata,
            SelfHostedRunner(
                identity=identity,
                busy=False,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.OFFLINE,
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
                identity=identity,
                busy=False,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.ONLINE,
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
                identity=identity,
                busy=True,
                id=1,
                labels=[],
                status=GitHubRunnerStatus.OFFLINE,
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

    identity = RunnerIdentity(instance_id=instance_id, metadata=metadata)
    runner_health = platform.get_runner_health(identity)

    assert runner_health
    assert runner_health.online is expected_online
    assert runner_health.busy is expected_busy
    assert runner_health.deletable is expected_deletable


@pytest.mark.parametrize(
    "requested_runners,github_runners,expected_health_response",
    [
        pytest.param(
            [],
            [],
            RunnersHealthResponse(),
            id="Nothing requested, nothing in github, nothing replied.",
        ),
        pytest.param(
            [
                identity_1 := RunnerIdentity(
                    InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(platform_name="github", runner_id=str(1)),
                ),
                identity_2 := RunnerIdentity(
                    InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(platform_name="github", runner_id=str(2)),
                ),
            ],
            [
                SelfHostedRunner(
                    identity=identity_1,
                    busy=True,
                    id=3,
                    labels=[],
                    status=GitHubRunnerStatus.ONLINE,
                    deletable=False,
                )
            ],
            RunnersHealthResponse(
                requested_runners=[
                    PlatformRunnerHealth(
                        identity=identity_1,
                        online=True,
                        busy=True,
                        deletable=False,
                    ),
                    PlatformRunnerHealth(
                        identity=identity_2,
                        online=False,
                        busy=False,
                        deletable=True,
                        runner_in_platform=False,
                    ),
                ]
            ),
            id="Two requested, only one in github.",
        ),
        pytest.param(
            [
                identity_1 := RunnerIdentity(
                    InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(platform_name="github", runner_id=str(1)),
                ),
            ],
            [
                SelfHostedRunner(
                    identity=identity_1,
                    busy=True,
                    id=3,
                    labels=[],
                    status=GitHubRunnerStatus.ONLINE,
                    deletable=False,
                ),
                SelfHostedRunner(
                    identity=(
                        identity_2 := RunnerIdentity(
                            InstanceID.build(prefix="unit-0"),
                            metadata=RunnerMetadata(platform_name="github", runner_id=str(2)),
                        )
                    ),
                    busy=True,
                    id=3,
                    labels=[],
                    status=GitHubRunnerStatus.ONLINE,
                    deletable=False,
                ),
            ],
            RunnersHealthResponse(
                requested_runners=[
                    PlatformRunnerHealth(
                        identity=identity_1,
                        online=True,
                        busy=True,
                        deletable=False,
                    ),
                ],
                non_requested_runners=[
                    identity_2,
                ],
            ),
            id="One requested, two in github.",
        ),
    ],
)
def test_get_runners_health(
    monkeypatch: pytest.MonkeyPatch,
    requested_runners: list[RunnerIdentity],
    github_runners: list[SelfHostedRunner],
    expected_health_response: RunnersHealthResponse,
):
    """
    arrange: Given some requested runner identities, and a reply from GitHub.
    act: Call get_runners_health.
    assert: The expected health response with the correct requested_runners
        and non_requested_runners.
    """
    prefix = "unit-0"

    github_client_mock = MagicMock(spec=GithubClient)
    github_client_mock.list_runners.return_value = github_runners

    platform = GitHubRunnerPlatform(prefix=prefix, path="org", github_client=github_client_mock)
    runners_health_response = platform.get_runners_health(requested_runners)

    assert runners_health_response == expected_health_response


def test_github_provider_delete_busy_runner_error():
    """
    arrange: given a mocked GitHub client that raises DeleteRunnerBusyError.
    act: when GitHubRunnerPlatform.delete_runners is called.
    assert: act: no ids are returned.
    """
    mock_github_client = MagicMock()
    mock_github_client.delete_runner.side_effect = DeleteRunnerBusyError
    github_provider = GitHubRunnerPlatform(
        prefix="test", path="test", github_client=mock_github_client
    )
    test_delete_ids = ["1", "2", "3"]

    assert github_provider.delete_runners(test_delete_ids) == []


def test_github_provider_delete_runners():
    """
    arrange: given a mocked GitHub client.
    act: when GitHubRunnerPlatform.delete_runners is called.
    assert: act: the deleted runner IDs are returned.
    """
    mock_github_client = MagicMock()
    github_provider = GitHubRunnerPlatform(
        prefix="test", path="test", github_client=mock_github_client
    )
    test_delete_ids = ["1", "2", "3"]

    assert sorted(github_provider.delete_runners(test_delete_ids)) == sorted(test_delete_ids)
