#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for the multiplexer provider module."""
import secrets
from unittest.mock import MagicMock

import pytest

from github_runner_manager.configuration import GitHubConfiguration, GitHubRepo
from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.platform.multiplexer_provider import MultiplexerPlatform
from github_runner_manager.platform.platform_provider import (
    PlatformError,
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)


def test_get_runners_health(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Given two platform providers and a multiplexer provider using both of them.
    act: Call get_runners_health.
    assert: The expected health response is returned combining the response from both
        providers.
    """
    prefix = "unit-0"

    github_provider_mock = MagicMock(spec=PlatformProvider)
    jobmanager_provider_mock = MagicMock(spec=PlatformProvider)

    platform = MultiplexerPlatform(
        {
            "github": github_provider_mock,
            "jobmanager": jobmanager_provider_mock,
        }
    )

    identity_github_1 = RunnerIdentity(
        instance_id=InstanceID.build(prefix=prefix),
        metadata=RunnerMetadata(platform_name="github", runner_id=str(1)),
    )
    identity_github_2 = RunnerIdentity(
        instance_id=InstanceID.build(prefix=prefix),
        metadata=RunnerMetadata(platform_name="github", runner_id=str(2)),
    )
    identity_jobmanager_1 = RunnerIdentity(
        instance_id=InstanceID.build(prefix=prefix),
        metadata=RunnerMetadata(platform_name="jobmanager", runner_id=str(1)),
    )
    identity_jobmanager_2 = RunnerIdentity(
        instance_id=InstanceID.build(prefix=prefix),
        metadata=RunnerMetadata(platform_name="jobmanager", runner_id=str(2)),
    )

    jobmanager_provider_mock.get_runners_health.return_value = RunnersHealthResponse(
        requested_runners=[
            health_identity_jobmanager_1 := PlatformRunnerHealth(
                identity=identity_jobmanager_1,
                online=True,
                busy=False,
                deletable=False,
            ),
        ],
        failed_requested_runners=[identity_jobmanager_2],
    )

    github_provider_mock.get_runners_health.return_value = RunnersHealthResponse(
        requested_runners=[
            health_identity_github_1 := PlatformRunnerHealth(
                identity=identity_github_1,
                online=True,
                busy=False,
                deletable=False,
            ),
        ],
        non_requested_runners=[identity_github_2],
    )

    requested_runners = [identity_github_1, identity_jobmanager_1, identity_jobmanager_2]
    runners_health_response = platform.get_runners_health(requested_runners)

    assert sorted(runners_health_response.requested_runners) == sorted(
        [health_identity_jobmanager_1, health_identity_github_1]
    )
    assert runners_health_response.failed_requested_runners == [identity_jobmanager_2]
    assert runners_health_response.non_requested_runners == [identity_github_2]


def test_get_runners_health_returns_non_requested_runners_always(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Prepare a github provider that replies with one non requested runner.
    act: Call get_runners_health without any requested runner.
    assert: The non requested runner is in the runner health response.
    """
    prefix = "unit-0"

    identity_github_1 = RunnerIdentity(
        instance_id=InstanceID.build(prefix=prefix),
        metadata=RunnerMetadata(platform_name="github", runner_id=str(1)),
    )

    github_provider_mock = MagicMock(spec=PlatformProvider)
    github_provider_mock.get_runners_health.return_value = RunnersHealthResponse(
        non_requested_runners=[identity_github_1],
    )

    platform = MultiplexerPlatform(
        {
            "github": github_provider_mock,
        }
    )

    runners_health_response = platform.get_runners_health(requested_runners=[])

    assert runners_health_response.requested_runners == []
    assert runners_health_response.failed_requested_runners == []
    assert runners_health_response.non_requested_runners == [identity_github_1]


@pytest.mark.parametrize(
    "github_config, jobmanager_config, expected_platforms",
    [
        pytest.param(
            GitHubConfiguration(
                token=secrets.token_hex(5),
                path=GitHubRepo(owner=secrets.token_hex(4), repo=secrets.token_hex(5)),
            ),
            None,
            {"github"},
            id="GitHub only",
        ),
        pytest.param(
            None,
            JobManagerConfiguration(url="http://jobmanager.example.com"),
            {"jobmanager"},
            id="JobManager only",
        ),
        pytest.param(
            GitHubConfiguration(
                token=secrets.token_hex(5),
                path=GitHubRepo(owner=secrets.token_hex(4), repo=secrets.token_hex(5)),
            ),
            JobManagerConfiguration(url="http://jobmanager.example.com"),
            {"github", "jobmanager"},
            id="Both GitHub and JobManager",
        ),
    ],
)
def test_multipexer_platform_build(
    github_config: GitHubConfiguration | None,
    jobmanager_config: JobManagerConfiguration | None,
    expected_platforms: set[str],
):
    """
    arrange: Either GitHub or JobManager configuration is provided.
    act: call build
    assert: no github or jobmanager in the multiplexer provider map
    """
    multiplexer = MultiplexerPlatform.build(
        prefix="unit-0",
        github_configuration=github_config,
        jobmanager_configuration=jobmanager_config,
    )

    assert expected_platforms == set(multiplexer._providers.keys())


def test_multipexer_platform_build_no_config_raises_error():
    """
    arrange: No configuration is provided.
    act: call build
    assert: raises ValueError
    """
    with pytest.raises(
        PlatformError, match="Either GitHub or JobManager configuration must be provided"
    ):
        MultiplexerPlatform.build(
            prefix="unit-0", github_configuration=None, jobmanager_configuration=None
        )
