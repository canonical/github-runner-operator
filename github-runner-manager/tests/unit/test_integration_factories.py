# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for integration test factories."""

from tests.integration.factories import GitHubConfig, create_default_config


def test_create_default_config_uses_token_auth_by_default():
    """
    arrange: A GitHub test config without GitHub App credentials.
    act: Build the integration test application config.
    assert: The GitHub auth block uses token auth.
    """
    config = create_default_config(
        github_config=GitHubConfig(
            token="ghp_test_token_1234567890abcdef",
            alt_token="ghp_test_alt_token_1234567890abcdef",
            path="canonical/example",
        )
    )

    assert config["github_config"]["auth"] == {"token": "ghp_test_token_1234567890abcdef"}


def test_create_default_config_uses_github_app_auth_when_available():
    """
    arrange: A GitHub test config with complete GitHub App credentials.
    act: Build the integration test application config.
    assert: The GitHub auth block uses GitHub App auth.
    """
    config = create_default_config(
        github_config=GitHubConfig(
            token="ghp_test_token_1234567890abcdef",
            alt_token="ghp_test_alt_token_1234567890abcdef",
            path="canonical/example",
            app_client_id="Iv23liExample",
            installation_id=456,
            private_key="-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
        )
    )

    assert config["github_config"]["auth"] == {
        "app_client_id": "Iv23liExample",
        "installation_id": 456,
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
    }
