# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for GitHub App authentication."""

import secrets

import pytest

from github_runner_manager.configuration.github import (
    GitHubAppAuth,
    GitHubPath,
    parse_github_path,
)
from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID


@pytest.fixture(autouse=True, scope="module")
def openstack_cleanup():
    """Override the autouse openstack_cleanup fixture — this module has no OpenStack dependency."""
    yield


@pytest.fixture(scope="module")
def github_app_auth(pytestconfig: pytest.Config) -> GitHubAppAuth:
    """Get GitHub App auth configuration, skip if credentials not provided."""
    app_client_id = pytestconfig.getoption("--github-app-client-id")
    installation_id = pytestconfig.getoption("--github-app-installation-id")
    private_key = pytestconfig.getoption("--github-app-private-key")

    if not all([app_client_id, installation_id, private_key]):
        pytest.skip("GitHub App credentials not provided")

    return GitHubAppAuth(
        app_client_id=app_client_id,
        installation_id=int(installation_id),
        private_key=private_key,
    )


@pytest.fixture(scope="module")
def github_app_client(github_app_auth: GitHubAppAuth) -> GithubClient:
    """Create a GithubClient using GitHub App authentication."""
    return GithubClient(auth=github_app_auth)


@pytest.fixture(scope="module")
def github_path(pytestconfig: pytest.Config) -> GitHubPath:
    """Get the GitHub path from test configuration."""
    path_str = pytestconfig.getoption("--github-repository")
    if not path_str:
        pytest.skip("GitHub repository path not provided")
    return parse_github_path(path_str, runner_group="default")


def test_get_jit_token_with_github_app_auth(
    github_app_client: GithubClient, github_path: GitHubPath
) -> None:
    """
    arrange: GithubClient created with GitHubAppAuth credentials.
    act: Request a JIT config token to register a runner.
    assert: Token is returned and runner is created, then clean up.
    """
    prefix = "test-app-auth"
    instance_id = InstanceID(prefix=prefix, suffix=secrets.token_hex(6))

    runner = None
    try:
        jit_token, runner = github_app_client.get_runner_registration_jittoken(
            github_path, instance_id=instance_id, labels=[prefix]
        )

        assert jit_token, "JIT config token should be non-empty"
        assert runner.id > 0
        assert runner.identity.instance_id == instance_id
    finally:
        if runner is not None:
            github_app_client.delete_runner(github_path, runner.id)
