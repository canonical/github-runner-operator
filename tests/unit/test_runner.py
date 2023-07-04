# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of Runner class."""

import secrets
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errors import RunnerCreateError, RunnerRemoveError
from runner import Runner, RunnerClients, RunnerConfig, RunnerStatus
from runner_type import GitHubOrg, GitHubRepo, VirtualMachineResources
from tests.unit.mock import (
    MockLxdClient,
    MockRepoPolicyComplianceClient,
    mock_lxd_error_func,
    mock_runner_error_func,
)


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


@pytest.fixture(scope="function", name="lxd")
def mock_lxd_client_fixture():
    return MockLxdClient()


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
def runner_fixture(request, lxd: MockLxdClient, tmp_path: Path):
    client = RunnerClients(
        MagicMock(),
        MagicMock(),
        lxd,
        MockRepoPolicyComplianceClient(),
    )
    pool_path = tmp_path / "test_storage"
    pool_path.mkdir(exist_ok=True)
    config = RunnerConfig("test_app", request.param[0], request.param[1], pool_path, "test_runner")
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
    lxd: MockLxdClient,
):
    """
    arrange: Nothing.
    act: Create a runner.
    assert: An lxd instance for the runner is created.
    """

    runner.create("test_image", vm_resources, binary_path, token)

    instances = lxd.instances.all()
    assert len(instances) == 1

    if runner.config.proxies:
        instance = instances[0]
        env_proxy = instance.files.read_file("/home/ubuntu/github-runner/.env")
        systemd_docker_proxy = instance.files.read_file(
            "/etc/systemd/system/docker.service.d/http-proxy.conf"
        )
        # Test the file has being written to.  This value does not contain the string as the
        # jinja2.environment.Environment is mocked with MagicMock.
        assert env_proxy is not None
        assert systemd_docker_proxy is not None


def test_create_lxd_fail(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Setup the create runner to fail with lxd error.
    act: Create a runner.
    assert: Correct exception should be thrown. Any created instance should be
        cleanup.
    """
    lxd.profiles.exists = mock_lxd_error_func

    with pytest.raises(RunnerCreateError):
        runner.create("test_image", vm_resources, binary_path, token)

    assert len(lxd.instances.all()) == 0


def test_create_runner_fail(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Setup the create runner to fail with runner error.
    act: Create a runner.
    assert: Correct exception should be thrown. Any created instance should be
        cleanup.
    """
    runner._clients.lxd.instances.create = mock_runner_error_func

    with pytest.raises(RunnerCreateError):
        runner.create("test_image", vm_resources, binary_path, token)


def test_remove(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Create a runner.
    act: Remove the runner.
    assert: The lxd instance for the runner is removed.
    """

    runner.create("test_image", vm_resources, binary_path, token)
    runner.remove("test_token")
    assert len(lxd.instances.all()) == 0


def test_remove_failed_instance(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Create a stopped runner that failed to remove itself.
    act: Remove the runner.
    assert: The lxd instance for the runner is removed.
    """
    # Cases where the ephemeral instance encountered errors and the status was Stopped but not
    # removed was found before.
    runner.create("test_image", vm_resources, binary_path, token)
    runner.instance.status = "Stopped"
    runner.remove("test_token")
    assert len(lxd.instances.all()) == 0


def test_remove_none(
    runner: Runner,
    token: str,
    lxd: MockLxdClient,
):
    """
    arrange: Not creating a runner.
    act: Remove the runner.
    assert: The lxd instance for the runner is removed.
    """

    runner.remove(token)
    assert len(lxd.instances.all()) == 0


def test_remove_with_stop_error(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Create a runner. Set up LXD stop fails with LxdError.
    act: Remove the runner.
    assert: RunnerRemoveError is raised.
    """
    runner.create("test_image", vm_resources, binary_path, token)
    runner.instance.stop = mock_lxd_error_func

    with pytest.raises(RunnerRemoveError):
        runner.remove("test_token")


def test_remove_with_delete_error(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
):
    """
    arrange: Create a runner. Set up LXD delete fails with LxdError.
    act: Remove the runner.
    assert: RunnerRemoveError is raised.
    """
    runner.create("test_image", vm_resources, binary_path, token)
    runner.instance.status = "Stopped"
    runner.instance.delete = mock_lxd_error_func

    with pytest.raises(RunnerRemoveError):
        runner.remove("test_token")
