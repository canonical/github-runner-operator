#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test for the platform factory module."""

from unittest.mock import MagicMock

import pytest

from github_runner_manager.platform.factory import platform_factory
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform


@pytest.mark.parametrize(
    "github_config, expected_error",
    [
        pytest.param(None, "Missing configuration.", id="No configurations"),
    ],
)
def test_platform_factory_invalid_configurations(github_config, expected_error):
    """
    arrange: mock github client configuration.
    act: call platform_factory with invalid configurations.
    assert: check that ValueError is raised.
    """
    with pytest.raises(ValueError) as exc_info:
        platform_factory(vm_prefix="test", github_config=github_config)
    assert str(exc_info.value) == expected_error


@pytest.mark.parametrize(
    "github_config, expected_platform",
    [
        pytest.param(MagicMock(), GitHubRunnerPlatform, id="GitHub configuration"),
    ],
)
def test_platform_factory(github_config, expected_platform):
    """
    arrange: mock github client configuration.
    act: call platform_factory with mock objects.
    assert: check that expected platform provider is returned.
    """
    assert isinstance(
        platform_factory(vm_prefix="test", github_config=github_config),
        expected_platform,
    )
