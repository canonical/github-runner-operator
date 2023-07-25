# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""


import argparse


def pytest_addoption(parser: argparse.ArgumentParser):
    """Add options to pytest parser."""
    # mypy cannot find the `addoption` attr.
    parser.addoption("--path", action="store")  # type: ignore
    parser.addoption("--token-one", action="store")  # type: ignore
    parser.addoption("--token-two", action="store")  # type: ignore
    parser.addoption("--http-proxy", action="store")  # type: ignore
    parser.addoption("--https-proxy", action="store")  # type: ignore
    parser.addoption("--no-proxy", action="store")  # type: ignore
