# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")
    parser.addoption(
        "--github-token",
        action="store",
        help="GitHub personal access token for integration tests.",
    )
    parser.addoption(
        "--github-repository",
        action="store",
        help="The GitHub repository in <owner>/<repo> format for integration tests.",
    )
    parser.addoption(
        "--github-token-alt",
        action="store",
        help="Alternate GitHub token from a different user for fork testing.",
    )
    parser.addoption(
        "--openstack-auth-url",
        action="store",
        help="OpenStack authentication URL for integration tests.",
    )
    parser.addoption(
        "--openstack-project",
        action="store",
        help="OpenStack project name for integration tests.",
    )
    parser.addoption(
        "--openstack-username",
        action="store",
        help="OpenStack username for integration tests.",
    )
    parser.addoption(
        "--openstack-password",
        action="store",
        help="OpenStack password for integration tests.",
    )
    parser.addoption(
        "--openstack-network",
        action="store",
        help="OpenStack network name for integration tests.",
    )
    parser.addoption(
        "--openstack-region",
        action="store",
        help="OpenStack region name for integration tests.",
    )
