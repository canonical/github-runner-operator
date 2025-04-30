#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for testing the general types."""
from typing import Any

import pytest
from pydantic import ValidationError

from github_runner_manager.configuration import ProxyConfig, SupportServiceConfig
from github_runner_manager.configuration.github import GitHubOrg, GitHubRepo, parse_github_path


@pytest.mark.parametrize(
    "proxy_config",
    [
        ProxyConfig(http=None, https=None, no_proxy=""),
        {"http": None, "https": None},
        None,
    ],
)
def test_check_use_aproxy(proxy_config: Any):
    """
    arrange: Using aproxy True and different options for the runner proxy without http nor https.
    act: Create the SupportServiceConfig object
    assert: Verify that the method raises a ValidationError with the expected message.
    """
    with pytest.raises(ValidationError) as exc_info:
        SupportServiceConfig(
            use_aproxy=True,
            runner_proxy_config=proxy_config,
            ssh_debug_connections=[],
        )
    assert "aproxy requires the runner http or https to be set" in str(exc_info.value)


@pytest.mark.parametrize(
    "http, https, expected_address, expected_host, expected_port",
    [
        ("http://proxy.example.com", None, "proxy.example.com", "proxy.example.com", None),
        (
            "http://proxy.example.com:3128",
            None,
            "proxy.example.com:3128",
            "proxy.example.com",
            "3128",
        ),
        (
            None,
            "https://secureproxy.example.com",
            "secureproxy.example.com",
            "secureproxy.example.com",
            None,
        ),
        (
            None,
            "http://secureproxy.example.com:3128",
            "secureproxy.example.com:3128",
            "secureproxy.example.com",
            "3128",
        ),
        (None, None, None, None, None),
    ],
)
def test_proxy_address(
    http: str | None,
    https: str | None,
    expected_address: str | None,
    expected_port: str | None,
    expected_host: str | None,
):
    """
    arrange: Create a ProxyConfig instance with specified HTTP, HTTPS, and aproxy settings.
    act: Access the aproxy_address property of the ProxyConfig instance.
    assert: Verify that the property returns the expected apropy address.
    """
    proxy_config = ProxyConfig(http=http, https=https)

    assert expected_address == proxy_config.proxy_address
    assert expected_port == proxy_config.proxy_port
    assert expected_host == proxy_config.proxy_host


def test_github_repo_path():
    """
    arrange: Create a GithubRepo instance with owner and repo attributes.
    act: Call the path method of the GithubRepo instance with a mock.
    assert: Verify that the returned path is constructed correctly.
    """
    owner = "test_owner"
    repo = "test_repo"
    github_repo = GitHubRepo(owner=owner, repo=repo)

    path = github_repo.path()

    assert path == f"{owner}/{repo}"


def test_github_org_path():
    """
    arrange: Create a GithubOrg instance with org and group attributes.
    act: Call the path method of the GithubOrg instance.
    assert: Verify that the returned path is constructed correctly.
    """
    org = "test_org"
    group = "test_group"
    github_org = GitHubOrg(org=org, group=group)

    path = github_org.path()

    assert path == org


@pytest.mark.parametrize(
    "path_str, runner_group, expected_type, expected_attrs",
    [
        ("owner/repo", "test_group", GitHubRepo, {"owner": "owner", "repo": "repo"}),
        ("test_org", "test_group", GitHubOrg, {"org": "test_org", "group": "test_group"}),
    ],
)
def test_parse_github_path(
    path_str: str,
    runner_group: str,
    expected_type: GitHubRepo | GitHubOrg,
    expected_attrs: dict[str, str],
):
    """
    arrange: Create different GitHub path strings and runner group names.
    act: Call parse_github_path with the given path string and runner group name.
    assert: Verify that the function returns the expected type and attributes.
    """
    result = parse_github_path(path_str, runner_group)

    # Assert
    assert isinstance(result, expected_type)
    for attr, value in expected_attrs.items():
        assert getattr(result, attr) == value
