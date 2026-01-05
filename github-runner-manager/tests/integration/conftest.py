# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github-runner-manager integration tests."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Generator

import openstack
import pytest
from github import Github
from github.Auth import Token
from github.Branch import Branch
from github.Repository import Repository

from .factories import GitHubConfig, OpenStackConfig, ProxyConfig, TestConfig

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
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
def openstack_config(pytestconfig: pytest.Config) -> OpenStackConfig:
    """Get OpenStack configuration from pytest options or environment.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        OpenStack configuration object.

    Raises:
        AssertionError: If not all required parameters are provided.
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


@pytest.fixture(scope="module")
def openstack_connection(
    openstack_config: OpenStackConfig,
) -> Generator[openstack.connection.Connection, None, None]:
    """Create OpenStack connection for the test module.

    Args:
        openstack_config: OpenStack configuration object or None.

    Yields:
        OpenStack connection object or None if no config provided.
    """
    conn = openstack.connect(
        auth_url=openstack_config.auth_url,
        project_name=openstack_config.project,
        username=openstack_config.username,
        password=openstack_config.password,
        user_domain_name=openstack_config.user_domain_name,
        project_domain_name=openstack_config.project_domain_name,
        region_name=openstack_config.region_name,
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True, scope="module")
def openstack_cleanup(
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
) -> Generator[None, None, None]:
    """Clean up OpenStack resources after test execution.

    Args:
        openstack_connection: OpenStack connection object or None.
        test_config: Test configuration with unique VM prefix.
        request: Pytest request fixture for accessing test outcome.

    Yields:
        None
    """
    yield

    logger.info("Cleaning up OpenStack resources with prefix: %s", test_config.vm_prefix)

    try:
        # Clean up servers
        servers = [
            server
            for server in openstack_connection.list_servers()
            if server.name.startswith(test_config.vm_prefix)
        ]
        for server in servers:
            logger.info("Fetching console log for server: %s", server.name)
            try:
                console_log = openstack_connection.get_server_console(server.id)
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
            openstack_connection.delete_server(server.id, wait=True)

        # Clean up keypairs
        keypairs = [
            keypair
            for keypair in openstack_connection.list_keypairs()
            if keypair.name.startswith(test_config.vm_prefix)
        ]
        for keypair in keypairs:
            logger.info("Deleting keypair: %s", keypair.name)
            openstack_connection.delete_keypair(keypair.name)

        # Clean up security groups (if named with prefix)
        security_groups = [
            sg
            for sg in openstack_connection.list_security_groups()
            if sg.name.startswith(f"{test_config.vm_prefix}-")
        ]
        for sg in security_groups:
            logger.info("Deleting security group: %s", sg.name)
            openstack_connection.delete_security_group(sg.id)

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


@pytest.fixture(scope="module")
def github_branch(
    github_repository: Repository, test_config: TestConfig
) -> Generator[Branch, None, None]:
    """Create a new branch for testing, from latest commit in current branch.

    Args:
        github_repository: GitHub repository object.

    Yields:
        Branch object for the created test branch.
    """
    test_branch = f"test-{test_config.test_id}"

    sha_result = subprocess.run(
        ["/usr/bin/git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    current_commit_sha = sha_result.stdout.strip()

    branch_ref = github_repository.create_git_ref(
        ref=f"refs/heads/{test_branch}", sha=current_commit_sha
    )

    # Wait for branch to be available, GitHub is eventually consistent
    timeout = 60
    retry_delay = 1
    start_time = time.time()
    branch = None

    while time.time() - start_time < timeout:
        try:
            branch = github_repository.get_branch(test_branch)
            logger.info("Created test branch: %s at SHA: %s", test_branch, current_commit_sha)
            break
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed < timeout:
                logger.debug(
                    "Branch %s not yet available (elapsed: %.1fs), retrying in %ds: %s",
                    test_branch,
                    elapsed,
                    retry_delay,
                    e,
                )
                time.sleep(retry_delay)
            else:
                logger.error("Failed to get branch %s after %.1fs", test_branch, elapsed)
                raise

    yield branch

    try:
        branch_ref.delete()
        logger.info("Deleted test branch: %s", test_branch)
    except Exception as e:
        logger.warning("Failed to delete test branch %s: %s", test_branch, e)


@pytest.fixture(scope="module")
def tmp_test_dir(tmp_path_factory) -> Path:
    """Create a temporary test directory.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Returns:
        Path to the created temporary test directory.
    """
    test_dir = tmp_path_factory.mktemp("integration_test")
    return test_dir
