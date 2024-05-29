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
        "--use-existing-app",
        action="store",
        help="The existing app to use."
        "This will skip deployment of the charm and use the existing app."
        "This option is useful for local testing."
        "It is expected that the existing app is already integrated with other apps "
        "like grafana-agent, etc. ",
    )
    # Openstack testing opts
    parser.addoption(
        "--openstack-network-name",
        action="store",
        help="The Openstack network to create testing instances under.",
        default=None,
    )
    parser.addoption(
        "--openstack-flavor-name",
        action="store",
        help="The Openstack flavor to create testing instances with.",
        default=None,
    )
    # microstack local testing option
    parser.addoption(
        "--openstack-clouds-yaml",
        action="store",
        help="The OpenStack clouds yaml file for the charm to use.",
        default=None,
    )
    # Private endpoint options
    parser.addoption(
        "--openstack-auth-url",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
        default=None,
    )
    parser.addoption(
        "--openstack-password",
        action="store",
        help="The password to authenticate to Openstack service.",
        default=None,
    )
    parser.addoption(
        "--openstack-project-domain-name",
        action="store",
        help="The Openstack project domain name to use.",
        default=None,
    )
    parser.addoption(
        "--openstack-project-name",
        action="store",
        help="The Openstack project name to use.",
        default=None,
    )
    parser.addoption(
        "--openstack-user-domain-name",
        action="store",
        help="The Openstack user domain name to use.",
        default=None,
    )
    parser.addoption(
        "--openstack-user-name",
        action="store",
        help="The Openstack user to authenticate as.",
        default=None,
    )
    parser.addoption(
        "--openstack-region-name",
        action="store",
        help="The Openstack region to authenticate to.",
        default=None,
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
