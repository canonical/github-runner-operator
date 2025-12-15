# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github-runner-manager integration tests."""

import logging
from pathlib import Path
from typing import Generator

import openstack
import pytest
from github import Github
from github.Auth import Token
from github.Repository import Repository

from .factories import GitHubConfig, OpenStackConfig, ProxyConfig, TestConfig

logger = logging.getLogger(__name__)


@pytest.fixture
def test_config(pytestconfig: pytest.Config) -> TestConfig:
    """Create a unique test configuration for parallel test execution.

    Returns:
        Test configuration with unique identifiers.
    """
    debug_log_dir = Path(pytestconfig.getoption("--debug-log-dir"))
    debug_log_dir.mkdir(parents=True, exist_ok=True)
    return TestConfig(debug_log_dir=debug_log_dir)


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
    alt_token = pytestconfig.getoption("--github-token-alt", None)
    path = pytestconfig.getoption("--github-repository")

    if not token or not alt_token or not path:
        pytest.fail(
            "GitHub configuration not provided. Use --github-token, --github-token-alt, and "
            "--github-repository options or set INTEGRATION_TOKEN, INTEGRATION_TOKEN_ALT, and "
            "GITHUB_REPOSITORY environment variables."
        )

    return GitHubConfig(token=token, alt_token=alt_token, path=path)


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
    user_domain_name = pytestconfig.getoption("--openstack-user-domain-name")
    project_domain_name = pytestconfig.getoption("--openstack-project-domain-name")
    flavor = pytestconfig.getoption("--openstack-flavor-name")
    image_id = pytestconfig.getoption("--openstack-image-id")

    # Only return config if all required parameters are provided
    assert all(
        [
            auth_url,
            project,
            project_domain_name,
            username,
            user_domain_name,
            password,
            network,
            region_name,
        ]
    ), "All OpenStack configurations must be supplied"

    return OpenStackConfig(
        auth_url=auth_url,
        project=project,
        username=username,
        password=password,
        network=network,
        region_name=region_name,
        user_domain_name=user_domain_name,
        project_domain_name=project_domain_name,
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


@pytest.fixture(autouse=True)
def openstack_cleanup(
    openstack_config: OpenStackConfig, test_config: TestConfig, request: pytest.FixtureRequest
) -> Generator[None, None, None]:
    """Clean up OpenStack resources after test execution.

    Args:
        openstack_config: OpenStack configuration for connection.
        test_config: Test configuration with unique VM prefix.
        request: Pytest request fixture for accessing test outcome.

    Yields:
        None
    """
    yield

    if not openstack_config:
        return

    logger.info("Cleaning up OpenStack resources with prefix: %s", test_config.vm_prefix)

    try:
        with openstack.connect(
            auth_url=openstack_config.auth_url,
            project_name=openstack_config.project,
            username=openstack_config.username,
            password=openstack_config.password,
            user_domain_name=openstack_config.user_domain_name,
            project_domain_name=openstack_config.project_domain_name,
            region_name=openstack_config.region_name,
        ) as conn:
            # Clean up servers
            servers = [
                server
                for server in conn.list_servers()
                if server.name.startswith(test_config.vm_prefix)
            ]
            for server in servers:
                logger.info("Fetching console log for server: %s", server.name)
                try:
                    console_log = conn.get_server_console(server.id)
                    if console_log:
                        log_file = test_config.debug_log_dir / f"{server.name}_console.log"
                        log_file.write_text(console_log, encoding="utf-8")
                        logger.info("Console log for server %s:\n%s", server.name, console_log)
                except Exception as log_error:
                    logger.warning(
                        "Failed to fetch console log for server %s: %s",
                        server.name,
                        log_error,
                    )

                logger.info("Deleting server: %s", server.name)
                conn.delete_server(server.id, wait=True)

            # Clean up keypairs
            keypairs = [
                keypair
                for keypair in conn.list_keypairs()
                if keypair.name.startswith(test_config.vm_prefix)
            ]
            for keypair in keypairs:
                logger.info("Deleting keypair: %s", keypair.name)
                conn.delete_keypair(keypair.name)

            # Clean up security groups (if named with prefix)
            security_groups = [
                sg
                for sg in conn.list_security_groups()
                if sg.name.startswith(f"{test_config.vm_prefix}-")
            ]
            for sg in security_groups:
                logger.info("Deleting security group: %s", sg.name)
                conn.delete_security_group(sg.id)

    except Exception as e:
        logger.error("Failed to clean up OpenStack resources: %s", e)


@pytest.fixture(scope="module")
def github_token(github_config: GitHubConfig) -> str:
    """Get GitHub token from github_config.

    Args:
        github_config: GitHub configuration object.

    Returns:
        GitHub personal access token.
    """
    return github_config.token


@pytest.fixture(scope="module")
def github_repository(github_config: GitHubConfig) -> Repository:
    """Get GitHub repository for testing.

    Args:
        github_config: GitHub configuration object.

    Returns:
        GitHub repository object.
    """
    auth = Token(github_config.token)
    github = Github(auth=auth)
    return github.get_repo(github_config.path)
