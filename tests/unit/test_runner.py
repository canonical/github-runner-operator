# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of Runner class."""

import secrets
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import jinja2
import pytest
from _pytest.monkeypatch import MonkeyPatch

from charm_state import GithubOrg, GithubRepo, SSHDebugConnection, VirtualMachineResources
from errors import CreateSharedFilesystemError, RunnerCreateError, RunnerRemoveError
from runner import CreateRunnerConfig, Runner, RunnerConfig, RunnerStatus
from runner_manager_type import RunnerManagerClients
from runner_type import ProxySetting
from shared_fs import SharedFilesystem
from tests.unit.factories import SSHDebugInfoFactory
from tests.unit.mock import (
    MockLxdClient,
    MockRepoPolicyComplianceClient,
    mock_lxd_error_func,
    mock_runner_error_func,
)

TEST_PROXY_SERVER_URL = "http://proxy.server:1234"


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


@pytest.fixture(autouse=True, scope="function", name="shared_fs")
def shared_fs_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the module for handling the Shared Filesystem."""
    mock = MagicMock()
    monkeypatch.setattr("runner.shared_fs", mock)
    return mock


@pytest.fixture(autouse=True, scope="function", name="exc_cmd_mock")
def exc_command_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the execution of a command."""
    exc_cmd_mock = MagicMock()
    monkeypatch.setattr("runner.execute_command", exc_cmd_mock)
    return exc_cmd_mock


@pytest.fixture(scope="function", name="jinja")
def jinja2_environment_fixture() -> MagicMock:
    """Mock the jinja2 environment.

    Provides distinct mocks for each template.
    """
    jinja2_mock = MagicMock(spec=jinja2.Environment)
    template_mocks = {
        "start.j2": MagicMock(),
        "pre-job.j2": MagicMock(),
        "env.j2": MagicMock(),
        "environment.j2": MagicMock(),
        "systemd-docker-proxy.j2": MagicMock(),
    }
    jinja2_mock.get_template.side_effect = lambda x: template_mocks.get(x, MagicMock())
    return jinja2_mock


@pytest.fixture(scope="function", name="ssh_debug_connections")
def ssh_debug_connections_fixture() -> list[SSHDebugConnection]:
    """A list of randomly generated ssh_debug_connections."""
    return SSHDebugInfoFactory.create_batch(size=100)


@pytest.fixture(
    scope="function",
    name="runner",
    params=[
        (
            GithubOrg("test_org", "test_group"),
            ProxySetting(no_proxy=None, http=None, https=None, aproxy_address=None),
        ),
        (
            GithubRepo("test_owner", "test_repo"),
            ProxySetting(
                no_proxy="test_no_proxy",
                http=TEST_PROXY_SERVER_URL,
                https=TEST_PROXY_SERVER_URL,
                aproxy_address=None,
            ),
        ),
    ],
)
def runner_fixture(
    request,
    lxd: MockLxdClient,
    jinja: MagicMock,
    tmp_path: Path,
    ssh_debug_connections: list[SSHDebugConnection],
):
    client = RunnerManagerClients(
        MagicMock(),
        jinja,
        lxd,
        MockRepoPolicyComplianceClient(),
    )
    pool_path = tmp_path / "test_storage"
    pool_path.mkdir(exist_ok=True)
    config = RunnerConfig(
        name="test_runner",
        app_name="test_app",
        path=request.param[0],
        proxies=request.param[1],
        lxd_storage_path=pool_path,
        labels=("test", "label"),
        dockerhub_mirror=None,
        issue_metrics=False,
        ssh_debug_connections=ssh_debug_connections,
    )
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

    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )

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
        runner.create(
            config=CreateRunnerConfig(
                image="test_image",
                resources=vm_resources,
                binary_path=binary_path,
                registration_token=token,
            )
        )

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
        runner.create(
            config=CreateRunnerConfig(
                image="test_image",
                resources=vm_resources,
                binary_path=binary_path,
                registration_token=token,
            )
        )


def test_create_with_metrics(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
    shared_fs: MagicMock,
    exc_cmd_mock: MagicMock,
    jinja: MagicMock,
):
    """
    arrange: Config the runner to issue metrics and mock the shared filesystem.
    act: Create a runner.
    assert: The command for adding a device has been executed and the templates are
        rendered to issue metrics.
    """

    runner.config.issue_metrics = True
    shared_fs.create.return_value = SharedFilesystem(
        path=Path("/home/ubuntu/shared_fs"), runner_name="test_runner"
    )
    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )

    exc_cmd_mock.assert_called_once_with(
        [
            "sudo",
            "lxc",
            "config",
            "device",
            "add",
            "test_runner",
            "metrics",
            "disk",
            "source=/home/ubuntu/shared_fs",
            "path=/metrics-exchange",
        ],
        check_exit=True,
    )

    jinja.get_template("start.j2").render.assert_called_once_with(issue_metrics=True)
    jinja.get_template("pre-job.j2").render.assert_called_once()
    assert "issue_metrics" in jinja.get_template("pre-job.j2").render.call_args[1]


def test_create_with_metrics_and_shared_fs_error(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
    lxd: MockLxdClient,
    shared_fs: MagicMock,
):
    """
    arrange: Config the runner to issue metrics and mock the shared filesystem module
     to throw an expected error.
    act: Create a runner.
    assert: The runner is created despite the error on the shared filesystem.
    """
    runner.config.issue_metrics = True
    shared_fs.create.side_effect = CreateSharedFilesystemError("")

    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )

    instances = lxd.instances.all()
    assert len(instances) == 1


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

    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )
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
    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )
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
    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )
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
    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )
    runner.instance.status = "Stopped"
    runner.instance.delete = mock_lxd_error_func

    with pytest.raises(RunnerRemoveError):
        runner.remove("test_token")


def test_random_ssh_connection_choice(
    runner: Runner,
    vm_resources: VirtualMachineResources,
    token: str,
    binary_path: Path,
):
    """
    arrange: given a mock runner with random batch of ssh debug infos.
    act: when runner.configure_runner is called.
    assert: selected ssh_debug_info is random.
    """
    runner.create(
        config=CreateRunnerConfig(
            image="test_image",
            resources=vm_resources,
            binary_path=binary_path,
            registration_token=token,
        )
    )
    runner._configure_runner()
    first_call_args = runner._clients.jinja.get_template("env.j2").render.call_args.kwargs
    runner._configure_runner()
    second_call_args = runner._clients.jinja.get_template("env.j2").render.call_args.kwargs

    assert first_call_args["ssh_debug_info"] != second_call_args["ssh_debug_info"], (
        "Same ssh debug info found, this may have occurred with a very low priority. "
        "Just try again."
    )
