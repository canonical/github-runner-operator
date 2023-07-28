# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

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

from tests.integration.helpers import check_runner_instance
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    """Metadata information of the charm."""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def app_name() -> str:
    """Randomized application name."""
    # Randomized app name to avoid collision when connecting to GitHub.
    return f"integration-{secrets.token_hex(4)}"


@pytest_asyncio.fixture(scope="module")
async def charm_path(
    ops_test: OpsTest, pytestconfig: pytest.Config, lxd_profile: Path
) -> AsyncIterator[Path]:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")

    if charm:
        yield Path(charm)

    yield await ops_test.build_charm(".")


@pytest.fixture(scope="module")
def path(pytestconfig: pytest.Config) -> str:
    """Configured path setting."""
    path = pytestconfig.getoption("--path")
    assert path, "Please specify the --path command line option"
    return path


@pytest.fixture(scope="module")
def token(pytestconfig: pytest.Config) -> str:
    """Configured token setting."""
    token = pytestconfig.getoption("--token")
    assert token, "Please specify the --token command line option"
    return token


@pytest.fixture(scope="module")
def token_alt(pytestconfig: pytest.Config, token: str) -> str:
    """Configured token_alt setting."""
    token_alt = pytestconfig.getoption("--token-alt")
    assert token_alt, "Please specify the --token-alt command line option"
    assert token_alt != token, "Please specify a different token for --token-alt"
    return token_alt


@pytest.fixture(scope="module")
def http_proxy(pytestconfig: pytest.Config) -> str:
    """Configured http_proxy setting."""
    http_proxy = pytestconfig.getoption("--http-proxy")
    return "" if http_proxy is None else http_proxy


@pytest.fixture(scope="module")
def https_proxy(pytestconfig: pytest.Config) -> str:
    """Configured https_proxy setting."""
    https_proxy = pytestconfig.getoption("--https-proxy")
    return "" if https_proxy is None else https_proxy


@pytest.fixture(scope="module")
def no_proxy(pytestconfig: pytest.Config) -> str:
    """Configured no_proxy setting."""
    no_proxy = pytestconfig.getoption("--no-proxy")
    return "" if no_proxy is None else no_proxy


@pytest.fixture(scope="module")
def model(ops_test: OpsTest) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None
    return ops_test.model


@pytest_asyncio.fixture(scope="module")
async def lxd_profile() -> AsyncIterator[Path]:
    """File containing LXD profile for test mode.

    The file needs to be in the charm directory while building a test version
    of the charm.
    """
    lxd_profile_path = Path("lxd-profile.yaml")

    lxd_profile_path.write_text(
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

    yield lxd_profile_path

    lxd_profile_path.unlink(missing_ok=True)


@pytest_asyncio.fixture(scope="module")
async def app_no_token(
    model: Model,
    charm_path: Path,
    app_name: str,
    path: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application with no token.

    Test should ensure it returns with the application having no token and no
    runner.
    """
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
        charm_path,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "virtual-machines": 0,
            "denylist": "10.10.0.0/16",
            "test-mode": "insecure",
        },
    )
    await model.wait_for_idle()

    yield application


@pytest_asyncio.fixture(scope="module")
async def app_no_runner(
    model: Model, app_no_token: Application, token: str
) -> AsyncIterator[Application]:
    """Application with no runner.

    The application might not have runner binary downloaded.

    Test should ensure it returns with the application in a good state and has
    no runner.
    """
    unit = app_no_token.units[0]

    await app_no_token.set_config({"token": token})
    await model.wait_for_idle()
    assert app_no_token.status == ACTIVE_STATUS_NAME

    # Wait until there is no runner.
    await check_runner_instance(unit, 0)

    yield app_no_token

    await app_no_token.set_config({"token": ""})
    await model.wait_for_idle()


@pytest_asyncio.fixture(scope="module")
async def app(model: Model, app_no_runner: Application) -> AsyncIterator[Application]:
    """Application with a single runner.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    unit = app_no_runner.units[0]

    action = await unit.run_action("update-runner-bin")
    await action.wait()

    await app_no_runner.set_config({"virtual-machines": "1"})
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle()
    assert app_no_runner.status == ACTIVE_STATUS_NAME

    # Wait until there is one runner.
    await check_runner_instance(unit, 1)

    yield app_no_runner

    await app_no_runner.set_config({"virtual-machines": "0"})
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle()
