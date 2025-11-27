# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github-runner-manager integration tests."""

import pytest

from .factories import GitHubConfig, OpenStackConfig, ProxyConfig, TestConfig


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
        pytest.fail: If neither --github-token option nor INTEGRATION_TOKEN
            environment variable is set.
    """
    token = pytestconfig.getoption("--github-token")
    path = pytestconfig.getoption("--github-repository")

    if not token or not path:
        pytest.fail(
            "GitHub configuration not provided. Use --github-token and --github-repository "
            "options or set INTEGRATION_TOKEN and GITHUB_REPOSITORY environment variables."
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
    flavor = pytestconfig.getoption("--openstack-flavor")
    image_id = pytestconfig.getoption("--openstack-image-id")

    # Only return config if all required parameters are provided
    assert all(
        [auth_url, project, username, password, network, region_name]
    ), "All OpenStack configurations must be supplied"

    return OpenStackConfig(
        auth_url=auth_url,
        project=project,
        username=username,
        password=password,
        network=network,
        region_name=region_name,
        flavor=flavor,
        image_id=image_id,
    )


@pytest.fixture(scope="module")
def proxy_config(pytestconfig: pytest.Config) -> ProxyConfig | None:
    """Get proxy configuration from pytest options or environment.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        Proxy configuration object, or None if no proxy is configured.
    """
    http_proxy = pytestconfig.getoption("--http-proxy")
    https_proxy = pytestconfig.getoption("--https-proxy")
    no_proxy = pytestconfig.getoption("--no-proxy")
    openstack_http_proxy = pytestconfig.getoption("--openstack-http-proxy")
    openstack_https_proxy = pytestconfig.getoption("--openstack-https-proxy")
    openstack_no_proxy = pytestconfig.getoption("--openstack-no-proxy")

    # Return None if no proxy is configured
    if not any([http_proxy, https_proxy, openstack_http_proxy, openstack_https_proxy]):
        return None

    return ProxyConfig(
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        openstack_http_proxy=openstack_http_proxy,
        openstack_https_proxy=openstack_https_proxy,
        openstack_no_proxy=openstack_no_proxy,
    )
