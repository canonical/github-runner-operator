# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

import os
import secrets
import subprocess
from pathlib import Path
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
import yaml
from juju.application import Application
from juju.model import Model
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    """Metadata information of the charm"""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def app_name() -> str:
    # Randomized app name to avoid collision while connecting to GitHub.
    return f"integration-{secrets.token_hex(4)}"


@pytest.fixture(scope="module")
def path(pytestconfig: pytest.Config) -> str:
    path = pytestconfig.getoption("--path")
    assert path, "Please specify the --path command line option"
    return path


@pytest.fixture(scope="module")
def token_one(pytestconfig: pytest.Config) -> str:
    token = pytestconfig.getoption("--token-one")
    assert token, "Please specify the --token-one command line option"
    return token


@pytest.fixture(scope="module")
def token_two(pytestconfig: pytest.Config, token_one: str) -> str:
    token = pytestconfig.getoption("--token-two")
    assert token, "Please specify the --token-two command line option"
    assert token != token_one, "Please specify a different token for --token-two"
    return token


@pytest.fixture(scope="module")
def http_proxy(pytestconfig: pytest.Config) -> str:
    http_proxy = pytestconfig.getoption("--http-proxy")
    return "" if http_proxy is None else http_proxy


@pytest.fixture(scope="module")
def https_proxy(pytestconfig: pytest.Config) -> str:
    https_proxy = pytestconfig.getoption("--https-proxy")
    return "" if https_proxy is None else https_proxy


@pytest.fixture(scope="module")
def no_proxy(pytestconfig: pytest.Config) -> str:
    no_proxy = pytestconfig.getoption("--no-proxy")
    return "" if no_proxy is None else no_proxy


@pytest.fixture(scope="module")
def model(ops_test: OpsTest) -> Model:
    assert ops_test.model is not None
    return ops_test.model


@pytest_asyncio.fixture(scope="module")
async def app(
    ops_test: OpsTest,
    model: Model,
    app_name: str,
    path: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    lxd_profile_path = Path("lxd-profile.yaml")
    with open(lxd_profile_path, "w") as profile_file:
        profile_file.writelines(
            """config:
    security.nesting: true
    security.privileged: true
    raw.lxc: |
        lxc.apparmor.profile=unconfined
        lxc.mount.auto=proc:rw sys:rw cgroup:rw
        lxc.cgroup.devices.allow=a
        lxc.cap.drop=
devices:
    kmsg:
        path: /dev/kmsg
        source: /dev/kmsg
        type: unix-char
"""
        )

    charm = await ops_test.build_charm(".")

    os.remove(lxd_profile_path)

    subprocess.run(["sudo", "modprobe", "br_netfilter"])
    await model.set_config(
        {
            "juju-http-proxy": http_proxy,
            "juju-https-proxy": https_proxy,
            "juju-no-proxy": no_proxy,
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )
    application = await model.deploy(
        charm,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "virtual-machines": 0,
            "test-mode": "insecure",
        },
    )

    yield application
