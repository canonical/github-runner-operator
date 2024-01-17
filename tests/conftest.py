# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""


from pytest import Parser


def pytest_addoption(parser: Parser):
    """Add options to pytest parser."""
    # The path to repository in <org>/<repo> or <user>/<repo> format.
    parser.addoption("--path", action="store")
    # The GitHub Personal Access Token.
    parser.addoption("--token", action="store")
    # The prebuilt github-runner-operator charm file.
    parser.addoption("--charm-file", action="store")
    # An alternative token to test repo-policy-compliance.
    parser.addoption("--token-alt", action="store")
    # HTTP proxy configuration value for juju model proxy configuration.
    parser.addoption("--http-proxy", action="store")
    # HTTPS proxy configuration value for juju model proxy configuration.
    parser.addoption("--https-proxy", action="store")
    # No proxy configuration value for juju model proxy configuration.
    parser.addoption("--no-proxy", action="store")
    parser.addoption("--loop-device", action="store")
