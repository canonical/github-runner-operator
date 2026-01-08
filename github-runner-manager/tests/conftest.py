# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""

import os


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption(
        "--github-token",
        action="store",
        help="GitHub personal access token for integration tests.",
        default=os.getenv("INTEGRATION_TOKEN"),
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
        default=os.getenv("INTEGRATION_TOKEN_ALT"),
    )
    parser.addoption(
        "--openstack-auth-url",
        action="store",
        help="OpenStack authentication URL for integration tests.",
        default=os.getenv("OS_AUTH_URL"),
    )
    parser.addoption(
        "--openstack-project-domain-name",
        action="store",
        help="OpenStack project domain name for integration tests.",
        default=os.getenv("OS_PROJECT_DOMAIN_NAME"),
    )
    parser.addoption(
        "--openstack-project",
        action="store",
        help="OpenStack project name for integration tests.",
        default=os.getenv("OS_PROJECT_NAME"),
    )
    parser.addoption(
        "--openstack-user-domain-name",
        action="store",
        help="OpenStack user domain name for integration tests.",
        default=os.getenv("OS_USER_DOMAIN_NAME"),
    )
    parser.addoption(
        "--openstack-username",
        action="store",
        help="OpenStack username for integration tests.",
        default=os.getenv("OS_USERNAME"),
    )
    parser.addoption(
        "--openstack-password",
        action="store",
        help="OpenStack password for integration tests.",
        default=os.getenv("OS_PASSWORD"),
    )
    parser.addoption(
        "--openstack-network",
        action="store",
        help="OpenStack network name for integration tests.",
        default=os.getenv("OS_NETWORK"),
    )
    parser.addoption(
        "--openstack-region",
        action="store",
        help="OpenStack region name for integration tests.",
        default=os.getenv("OS_REGION_NAME"),
    )
    parser.addoption(
        "--https-proxy",
        action="store",
        help="HTTPS proxy for runner configuration.",
        default=os.getenv("HTTPS_PROXY"),
    )
    parser.addoption(
        "--http-proxy",
        action="store",
        help="HTTP proxy for runner configuration.",
        default=os.getenv("HTTP_PROXY"),
    )
    parser.addoption(
        "--no-proxy",
        action="store",
        help="No proxy configuration for runner.",
        default=os.getenv("NO_PROXY"),
    )
    parser.addoption(
        "--openstack-https-proxy",
        action="store",
        help="HTTPS proxy for OpenStack runner operations.",
        default=os.getenv("OPENSTACK_HTTPS_PROXY"),
    )
    parser.addoption(
        "--openstack-http-proxy",
        action="store",
        help="HTTP proxy for OpenStack runner operations.",
        default=os.getenv("OPENSTACK_HTTP_PROXY"),
    )
    parser.addoption(
        "--openstack-no-proxy",
        action="store",
        help="No proxy configuration for OpenStack runner operations.",
        default=os.getenv("OPENSTACK_NO_PROXY"),
    )
    parser.addoption(
        "--openstack-flavor-name",
        action="store",
        help="OpenStack flavor name for runner instances.",
        default=os.getenv("OPENSTACK_FLAVOR_NAME"),
    )
    parser.addoption(
        "--openstack-image-id",
        action="store",
        help="OpenStack image ID for runner instances.",
        default=os.getenv("OPENSTACK_IMAGE_ID"),
    )
    parser.addoption(
        "--tmate-image",
        action="store",
        help="Tmate image for SSH server.",
        default=os.getenv("TMATE_IMAGE", "tmate/tmate-ssh-server:latest"),
    )
    parser.addoption(
        "--debug-log-dir",
        action="store",
        help="Directory to store debug logs.",
        default=os.getenv("DEBUG_LOG_DIR", "/tmp/github-runner-manager-test-logs"),
    )
