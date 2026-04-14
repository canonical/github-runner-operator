# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""

import os

import pytest
from pytest import Parser


def pytest_addoption(parser: Parser):
    """Add options to pytest parser.

    Args:
        parser: The pytest argument parser.
    """
    parser.addoption(
        "--path",
        action="store",
        help="The path to repository in <org>/<repo> or <user>/<repo> format.",
    )
    parser.addoption(
        "--token",
        action="store",
        help=(
            "An optionally comma separated GitHub Personal Access Token(s). "
            "Add more than one to help reduce rate limiting."
        ),
        default=os.environ.get("INTEGRATION_TOKEN"),
    )
    parser.addoption(
        "--charm-file",
        action="append",
        help="The prebuilt github-runner-operator charm file.",
        default=[],
    )
    parser.addoption(
        "--base",
        action="store",
        default="22.04",
        help=(
            "Ubuntu base token (e.g., 22.04, 24.04). Used to select the matching charm"
            " artifact when multiple --charm-file values are provided."
        ),
    )
    parser.addoption(
        "--http-proxy",
        action="store",
        help="HTTP proxy configuration value for juju model proxy configuration.",
    )
    parser.addoption(
        "--https-proxy",
        action="store",
        help="HTTPS proxy configuration value for juju model proxy configuration.",
    )
    parser.addoption(
        "--no-proxy",
        action="store",
        help="No proxy configuration value for juju model proxy configuration.",
    )
    parser.addoption(
        "--use-existing-app-suffix",
        action="store",
        help="The existing app suffix to use."
        "This will skip deployment of the charm and use the existing app."
        "This option is useful for local testing."
        "It is expected that the existing app is already integrated with other apps "
        "like grafana-agent, etc. ",
    )
    # Private endpoint shared options
    parser.addoption(
        "--openstack-http-proxy",
        action="store",
        help="The http proxy used to openstack integration.",
        default=None,
    )
    parser.addoption(
        "--openstack-https-proxy",
        action="store",
        help="The https proxy used to openstack integration.",
        default=None,
    )
    parser.addoption(
        "--openstack-no-proxy",
        action="store",
        help="The no proxy used to openstack integration.",
        default=None,
    )
    # Private endpoint options AMD64
    parser.addoption(
        "--openstack-network-name",
        action="store",
        help="The Openstack network to create testing instances under.",
        default=os.environ.get("OS_NETWORK"),
    )
    parser.addoption(
        "--openstack-flavor-name",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    parser.addoption(
        "--openstack-auth-url",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
        default=os.environ.get("OS_AUTH_URL"),
    )
    parser.addoption(
        "--openstack-password",
        action="store",
        help="The password to authenticate to Openstack service.",
        default=os.environ.get("OS_PASSWORD"),
    )
    parser.addoption(
        "--openstack-project-domain-name",
        action="store",
        help="The Openstack project domain name to use.",
        default=os.environ.get("OS_PROJECT_DOMAIN_NAME"),
    )
    parser.addoption(
        "--openstack-project-name",
        action="store",
        help="The Openstack project name to use.",
        default=os.environ.get("OS_PROJECT_NAME"),
    )
    parser.addoption(
        "--openstack-user-domain-name",
        action="store",
        help="The Openstack user domain name to use.",
        default=os.environ.get("OS_USER_DOMAIN_NAME"),
    )
    parser.addoption(
        "--openstack-username",
        action="store",
        help="The Openstack user to authenticate as.",
        default=os.environ.get("OS_USERNAME"),
    )
    parser.addoption(
        "--openstack-region-name",
        action="store",
        help="The Openstack region to authenticate to.",
        default=os.environ.get("OS_REGION_NAME"),
    )
    # Interface testing args
    parser.addoption(
        "--openstack-test-image",
        action="store",
        help="The image for testing openstack interfaces. Any ubuntu image should work.",
        default=None,
    )
    parser.addoption(
        "--openstack-test-flavor",
        action="store",
        help="The flavor for testing openstack interfaces. The resource should be enough to boot the test image.",
        default=None,
    )
    parser.addoption(
        "--openstack-image-id",
        action="store",
        help="The image ID to use for testing. If provided, any-charm will be used to mock the "
        "image builder for faster testing deployment.",
        default=None,
    )
    parser.addoption(
        "--dockerhub-mirror",
        action="store",
        help="The DockerHub mirror URL to use for testing.",
        default=None,
    )
    parser.addoption(
        "--github-app-client-id",
        action="store",
        help="The GitHub App Client ID for GitHub App authentication testing.",
        default=os.environ.get("GITHUB_APP_CLIENT_ID"),
    )
    parser.addoption(
        "--github-app-installation-id",
        action="store",
        help="The GitHub App installation ID for GitHub App authentication testing.",
        default=os.environ.get("GITHUB_APP_INSTALLATION_ID"),
    )
    parser.addoption(
        "--github-app-private-key",
        action="store",
        help="The GitHub App PEM-encoded private key for GitHub App authentication testing.",
        default=os.environ.get("GITHUB_APP_PRIVATE_KEY"),
    )
    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="Keep temporary Juju models after test runs.",
    )


def pytest_configure(config: pytest.Config):
    """Register custom markers.

    Args:
        config: The pytest Config object.
    """
    config.addinivalue_line("markers", "abort_on_fail: skip remaining tests after a failure")


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Record abort_on_fail failures so subsequent tests in the module are skipped.

    Args:
        item: The test item.
        call: The test call info.
    """
    if call.when == "call" and call.excinfo is not None:
        if any(item.iter_markers("abort_on_fail")):
            item.session._abort_on_fail_module = item.module  # type: ignore[attr-defined]


def pytest_runtest_setup(item: pytest.Item):
    """Skip tests if a prior abort_on_fail test in the same module failed.

    Args:
        item: The test item.
    """
    failed_mod = getattr(item.session, "_abort_on_fail_module", None)
    if failed_mod is not None and item.module is failed_mod:
        pytest.skip("skipped: prior abort_on_fail test failed")
