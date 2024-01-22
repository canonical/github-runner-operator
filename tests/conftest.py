# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""


from pytest import Parser


def pytest_addoption(parser: Parser):
    """Add options to pytest parser."""
    parser.addoption(
        "--path",
        action="store",
        help="The path to repository in <org>/<repo> or <user>/<repo> format.",
    )
    parser.addoption("--token", action="store", help="The GitHub Personal Access Token.")
    parser.addoption(
        "--charm-file", action="store", help="The prebuilt github-runner-operator charm file."
    )
    parser.addoption(
        "--token-alt", action="store", help="An alternative token to test repo-policy-compliance."
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
