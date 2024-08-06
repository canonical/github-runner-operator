# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""


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
    )
    parser.addoption(
        "--charm-file", action="store", help="The prebuilt github-runner-operator charm file."
    )
    parser.addoption(
        "--token-alt", action="store", help="An alternative token to test the change of a token."
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
        "--loop-device",
        action="store",
        help="The loop device to create shared FS for metrics logging",
    )
    parser.addoption(
        "--openstack-clouds-yaml",
        action="store",
        help="The OpenStack clouds yaml file for the charm to use.",
        default="",
    )
    parser.addoption(
        "--use-existing-app",
        action="store",
        help="The existing app to use."
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
        "--openstack-network-name-amd64",
        action="store",
        help="The Openstack network to create testing instances under.",
    )
    parser.addoption(
        "--openstack-flavor-name-amd64",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    parser.addoption(
        "--openstack-auth-url-amd64",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
    )
    parser.addoption(
        "--openstack-password-amd64",
        action="store",
        help="The password to authenticate to Openstack service.",
    )
    parser.addoption(
        "--openstack-project-domain-name-amd64",
        action="store",
        help="The Openstack project domain name to use.",
    )
    parser.addoption(
        "--openstack-project-name-amd64",
        action="store",
        help="The Openstack project name to use.",
    )
    parser.addoption(
        "--openstack-user-domain-name-amd64",
        action="store",
        help="The Openstack user domain name to use.",
    )
    parser.addoption(
        "--openstack-username-amd64",
        action="store",
        help="The Openstack user to authenticate as.",
    )
    parser.addoption(
        "--openstack-region-name-amd64",
        action="store",
        help="The Openstack region to authenticate to.",
    )
    # Private endpoint options ARM64
    parser.addoption(
        "--openstack-network-name-arm64",
        action="store",
        help="The Openstack network to create testing instances under.",
    )
    parser.addoption(
        "--openstack-flavor-name-arm64",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    parser.addoption(
        "--openstack-auth-url-arm64",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
    )
    parser.addoption(
        "--openstack-password-arm64",
        action="store",
        help="The password to authenticate to Openstack service.",
    )
    parser.addoption(
        "--openstack-project-domain-name-arm64",
        action="store",
        help="The Openstack project domain name to use.",
    )
    parser.addoption(
        "--openstack-project-name-arm64",
        action="store",
        help="The Openstack project name to use.",
    )
    parser.addoption(
        "--openstack-user-domain-name-arm64",
        action="store",
        help="The Openstack user domain name to use.",
    )
    parser.addoption(
        "--openstack-username-arm64",
        action="store",
        help="The Openstack user to authenticate as.",
    )
    parser.addoption(
        "--openstack-region-name-arm64",
        action="store",
        help="The Openstack region to authenticate to.",
    )
    # OpenStack integration tests
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
