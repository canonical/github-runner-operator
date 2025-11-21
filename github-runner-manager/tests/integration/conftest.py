# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github-runner-manager integration tests."""

import pytest

from .factories import GitHubConfig, OpenStackConfig, TestConfig


@pytest.fixture
def test_config() -> TestConfig:
    """Create a unique test configuration for parallel test execution.

    Returns:
        Test configuration with unique identifiers.
    """
    return TestConfig()


@pytest.fixture(scope="module")
def github_config(pytestconfig: pytest.Config) -> GitHubConfig:
    """Get GitHub configuration from pytest options or environment.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        GitHub configuration object.

    Raises:
        pytest.skip: If neither --github-token option nor GITHUB_TOKEN
            environment variable is set.
    """
    token = pytestconfig.getoption("--github-token")
    path = pytestconfig.getoption("--github-repository")

    if not token or not path:
        pytest.skip(
            "GitHub configuration not provided. Use --github-token and --github-repository "
            "options or set GITHUB_TOKEN and GITHUB_REPOSITORY environment variables."
        )

    return GitHubConfig(token=token, path=path)


@pytest.fixture(scope="module")
def openstack_config(pytestconfig: pytest.Config) -> OpenStackConfig | None:
    """Get OpenStack configuration from pytest options or environment.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        OpenStack configuration object, or None if not all parameters are provided.
    """
    auth_url = pytestconfig.getoption("--openstack-auth-url")
    project = pytestconfig.getoption("--openstack-project")
    username = pytestconfig.getoption("--openstack-username")
    password = pytestconfig.getoption("--openstack-password")
    network = pytestconfig.getoption("--openstack-network")
    region_name = pytestconfig.getoption("--openstack-region")

    # Only return config if all required parameters are provided
    if all([auth_url, project, username, password, network, region_name]):
        return OpenStackConfig(
            auth_url=auth_url,
            project=project,
            username=username,
            password=password,
            network=network,
            region_name=region_name,
        )
    return None
