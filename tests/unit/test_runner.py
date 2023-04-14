# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of Runner class."""

import secrets
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errors import RunnerCreateError
from runner import Runner, RunnerClients, RunnerConfig, RunnerStatus
from runner_type import GitHubOrg, GitHubRepo, VirtualMachineResources
from tests.unit.mock import MockPylxdClient, mock_pylxd_error_func, mock_runner_error_func


@pytest.fixture(scope="module", name="vm_resources")
def vm_resources_fixture():
    return VirtualMachineResources(2, "7Gib", "10Gib")


@pytest.fixture(scope="function", name="token")
def token_fixture():
    return secrets.token_hex()


@pytest.fixture(scope="function", name="binary_path")
def binary_path_fixture(tmp_path: Path):
    return tmp_path / "test_binary"


@pytest.fixture(scope="module", name="instance", params=["Running", "Stopped", None])
def instance_fixture(request):
    if request.param[0] is None:
        return None

    attrs = {"status": request.param[0], "execute.return_value": (0, "", "")}
    instance = unittest.mock.MagicMock(**attrs)
    return instance


@pytest.fixture(scope="function", name="pylxd")
def mock_pylxd_client_fixture():
    return MockPylxdClient()


@pytest.fixture(
    scope="function",
    name="runner",
    params=[
        (GitHubOrg("test_org", "test_group"), {}),
        (
            GitHubRepo("test_owner", "test_repo"),
            {"no_proxy": "test_no_proxy", "http": "test_http", "https": "test_https"},
        ),
    ],
)
def runner_fixture(request, pylxd: MockPylxdClient):
    client = RunnerClients(MagicMock(), MagicMock(), pylxd)
    config = RunnerConfig("test_app", request.param[0], request.param[1], "test_runner")
    status = RunnerStatus()
    return Runner(
        client,
        config,
        status,
    )


def test_create(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    pylxd: MockPylxdClient,
):
    """
    arrange: Nothing.
    act: Create a runner.
    assert: An pylxd instance for the runner is created.
    """

    runner.create("test_image", vm_resources, binary_path, token)

    instances = pylxd.instances.all()
    assert len(instances) == 1

    if runner.config.proxies:
        instance = instances[0]
        env_proxy = instance.files.get("/opt/github-runner/.env")
        systemd_docker_proxy = instance.files.get(
            "/etc/systemd/system/docker.service.d/http-proxy.conf"
        )
        # Test the file has being written.  This value does not contain the string as the
        # jinja2.environment.Environment is mocked with MagicMock.
        assert env_proxy is not None
        assert systemd_docker_proxy is not None


def test_create_pylxd_fail(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    pylxd: MockPylxdClient,
):
    """
    arrange: Setup the create runner to fail with pylxd error.
    act: Create a runner.
    assert: Correct exception should be thrown. Any created instance should be
        cleanup.
    """
    pylxd.profiles.exists = mock_pylxd_error_func

    with pytest.raises(RunnerCreateError):
        runner.create("test_image", vm_resources, binary_path, token)

    assert len(pylxd.instances.all()) == 0


def test_create_runner_fail(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    pylxd: MockPylxdClient,
):
    """
    arrange: Setup the create runner to fail with runner error.
    act: Create a runner.
    assert: Correct exception should be thrown. Any created instance should be
        cleanup.
    """
    runner._execute = mock_runner_error_func

    with pytest.raises(RunnerCreateError):
        runner.create("test_image", vm_resources, binary_path, token)


def test_remove(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    pylxd: MockPylxdClient,
):
    """
    arrange: Create a runner.
    act: Remove the runner.
    assert: The pylxd instance for the runner is removed.
    """

    runner.create("test_image", vm_resources, binary_path, token)
    runner.remove("test_token")
    assert len(pylxd.instances.all()) == 0


def test_remove_none(
    runner: Runner,
    token: str,
    pylxd: MockPylxdClient,
):
    """
    arrange: Not creating a runner.
    act: Remove the runner.
    assert: The pylxd instance for the runner is removed.
    """

    runner.remove(token)
    assert len(pylxd.instances.all()) == 0
