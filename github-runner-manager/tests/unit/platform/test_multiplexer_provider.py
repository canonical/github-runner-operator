#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for the multiplexer provider module."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.platform.multiplexer_provider import MultiplexerPlatform
from github_runner_manager.platform.platform_provider import (
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


def test_multiplexer_build_without_github():
    """
    arrange: no GithubConfiguration.
    act: call build
    assert: no github in the multiplexer provider map
    """
    github_config = None

    multiplexer = MultiplexerPlatform.build(
        prefix="unit-0",
        github_configuration=github_config,
    )

    assert "github" not in multiplexer._providers
