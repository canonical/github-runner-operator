# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

import secrets
import zipfile
from pathlib import Path
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
import yaml
from github import Github
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from pytest_operator.plugin import OpsTest

from tests.integration.helpers import create_runner, deploy_github_runner_charm
from tests.status_name import ACTIVE_STATUS_NAME

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    """Metadata information of the charm."""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def app_name() -> str:
    """Randomized application name."""
    # Randomized app name to avoid collision when runner is connecting to GitHub.
    return f"integration-id{secrets.token_hex(2)}"


@pytest.fixture(scope="module")
def charm_file(pytestconfig: pytest.Config) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "Please specify the --charm-file command line option"

    with zipfile.ZipFile(charm, mode="a") as charm_file:
        charm_file.writestr(
            "lxd-profile.yaml",
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
""",
        )
    return f"./{charm}"


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


@pytest.fixture(scope="module")
def github_client(token: str) -> Github:
    """Returns the github client."""
    return Github(token)


@pytest.fixture(scope="module")
def github_repository(github_client: Github, path: str) -> Repository:
    """Returns client to the Github repository."""
    return github_client.get_repo(path)


@pytest_asyncio.fixture(scope="module")
async def app_no_runner(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application with no runner."""
    # Set the scheduled event to 1 hour to avoid interfering with the tests.
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=path,
        token=token,
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
    )
    yield application


@pytest_asyncio.fixture(scope="module")
async def app(model: Model, app_no_runner: Application) -> AsyncIterator[Application]:
    """Application with a single runner.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    await create_runner(app=app_no_runner, model=model)

    yield app_no_runner


@pytest_asyncio.fixture(scope="module")
async def app_scheduled_events(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application with no token.

    Test should ensure it returns with the application having one runner.

    This fixture has to deploy a new application. The scheduled events are set
    to one hour in other application to avoid conflicting with the tests.
    Changes to the duration of scheduled interval only takes effect after the
    next trigger. Therefore, it would take a hour for the duration change to
    take effect.
    """
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=path,
        token=token,
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=8,
    )
    unit = application.units[0]

    await application.set_config({"virtual-machines": "1"})
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    yield application


@pytest_asyncio.fixture(scope="module")
async def app_runner(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application to test runners."""
    # Use a different app_name so workflows can select runners from this deployment.
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=f"{app_name}-test",
        path=path,
        token=token,
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
    )
    yield application
