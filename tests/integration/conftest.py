# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from ops.model import Application
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
def metadata() -> dict[str, any]:
    """Metadata information of the charm"""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def path(pytestconfig: pytest.Config) -> str:
    path = pytestconfig.getoption("--path")
    assert path is not None, "Please specify the --path command line option"
    return path


@pytest.fixture(scope="module")
def token(pytestconfig: pytest.Config) -> str:
    token = pytestconfig.getoption("--token")
    assert token is not None, "Please specify the --token command line option"
    return token


@pytest.fixture(scope="module")
def http_proxy(pytestconfig: pytest.Config) -> str:
    http_proxy = pytestconfig.getoption("--http-proxy")
    assert http_proxy is not None, "Please specify the --http-proxy command line option"
    return http_proxy


@pytest.fixture(scope="module")
def https_proxy(pytestconfig: pytest.Config) -> str:
    https_proxy = pytestconfig.getoption("--https-proxy")
    assert https_proxy is not None, "Please specify the --https-proxy command line option"
    return https_proxy


@pytest.fixture(scope="module")
def no_proxy(pytestconfig: pytest.Config) -> str:
    no_proxy = pytestconfig.getoption("--no-proxy")
    assert no_proxy is not None, "Please specify the --no-proxy command line option"
    return no_proxy


@pytest_asyncio.fixture(scope="module")
async def app(
    ops_test: OpsTest, path: str, http_proxy: str, https_proxy: str, no_proxy: str
) -> Application:
    charm = await ops_test.build_charm(".")

    await ops_test.model.set_constraints({"virt-type": "virtual-machine"})
    await ops_test.model.set_config(
        {"juju-http-proxy": http_proxy, "juju-https-proxy": https_proxy, "juju-no-proxy": no_proxy}
    )
    application = await ops_test.model.deploy(
        charm,
        series="jammy",
        config={"path": path, "virtual-machines": 1, "denylist": "10.0.0.0/8"},
        constraints={"cores": 4, "mem": 32},
    )

    yield application
