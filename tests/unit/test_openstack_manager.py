#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import random
import secrets
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, call

import jinja2
import openstack.connection
import openstack.exceptions
import pytest
from fabric.connection import Connection as SshConnection
from invoke import Result
from openstack.compute.v2.keypair import Keypair
from openstack.compute.v2.server import Server

import metrics.storage
from charm_state import CharmState, ProxyConfig, RepoPolicyComplianceConfig
from errors import OpenStackError, RunnerStartError
from github_type import GitHubRunnerStatus, RunnerApplication, SelfHostedRunner
from metrics import events as metric_events
from metrics.runner import RUNNER_INSTALLED_TS_FILE_NAME
from metrics.storage import MetricsStorage
from openstack_cloud import openstack_manager
from openstack_cloud.openstack_manager import MAX_METRICS_FILE_SIZE, METRICS_EXCHANGE_PATH
from runner_type import RunnerByHealth, RunnerGithubInfo
from tests.unit import factories

CLOUD_NAME = "microstack"


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack_connect_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    monkeypatch.setattr("openstack_cloud.openstack_manager.openstack.connect", mock_connect)
    return mock_connect


@pytest.fixture(name="mock_server")
def mock_server_fixture() -> MagicMock:
    """Mock OpenStack Server object."""
    mock_server = MagicMock(spec=Server)
    mock_server.key_name = "mock_key"
    mock_server.addresses.values = MagicMock(return_value=[[{"addr": "10.0.0.1"}]])
    return mock_server


@pytest.fixture(name="patch_get_ssh_connection_health_check")
def patch_get_ssh_connection_health_check_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch SSH connection to a MagicMock instance for get_ssh_connection health check."""
    mock_get_ssh_connection = MagicMock(
        spec=openstack_manager.OpenstackRunnerManager._get_ssh_connection
    )
    mock_ssh_connection = MagicMock(spec=SshConnection)
    mock_ssh_connection.host = "test host IP"
    mock_result = MagicMock(spec=Result)
    mock_result.ok = True
    mock_result.stderr = ""
    mock_result.stdout = "hello world"
    mock_ssh_connection.run.return_value = mock_result
    mock_get_ssh_connection.return_value = [mock_ssh_connection]

    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_ssh_connection",
        mock_get_ssh_connection,
    )


@pytest.fixture(name="ssh_connection_health_check")
def ssh_connection_health_check_fixture(monkeypatch: pytest.MonkeyPatch):
    """SSH connection to a MagicMock instance for health check."""
    mock_get_ssh_connection = MagicMock(
        spec=openstack_manager.OpenstackRunnerManager._get_ssh_connection
    )
    mock_ssh_connection = MagicMock(spec=SshConnection)
    mock_ssh_connection.host = "test host IP"
    mock_result = MagicMock(spec=Result)
    mock_result.ok = True
    mock_result.stderr = ""
    mock_result.stdout = "-- Test output: /bin/bash /home/ubuntu/actions-runner/run.sh --"
    mock_ssh_connection.run.return_value = mock_result
    mock_get_ssh_connection.return_value = mock_ssh_connection

    return mock_get_ssh_connection


@pytest.fixture(name="patch_ssh_connection_error")
def patch_ssh_connection_error_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch SSH connection to a MagicMock instance with error on run."""
    mock_get_ssh_connection = MagicMock(
        spec=openstack_manager.OpenstackRunnerManager._get_ssh_connection
    )
    mock_ssh_connection = MagicMock(spec=SshConnection)
    mock_result = MagicMock(spec=Result)
    mock_result.ok = False
    mock_result.stdout = "Mock stdout"
    mock_result.stderr = "Mock stderr"
    mock_ssh_connection.run.return_value = mock_result
    mock_get_ssh_connection.return_value = mock_ssh_connection

    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_ssh_connection",
        mock_get_ssh_connection,
    )


@pytest.fixture(name="mock_github_client")
def mock_github_client_fixture() -> MagicMock:
    """Mocked github client that returns runner application."""
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.return_value = RunnerApplication(
        os="linux",
        architecture="x64",
        download_url="http://test_url",
        filename="test_filename",
        temp_download_token="test_token",
    )
    mock_github_client.get_runner_registration_token.return_value = "test_token"
    return mock_github_client


@pytest.fixture(name="patch_execute_command")
def patch_execute_command_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch execute command to a MagicMock instance."""
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(spec=openstack_manager.execute_command),
    )


@pytest.fixture(name="patched_create_connection_context")
def patched_create_connection_context_fixture(monkeypatch: pytest.MonkeyPatch):
    """Return a mocked openstack connection context manager and patch create_connection."""
    mock_connection = MagicMock(spec=openstack_manager.openstack.connection.Connection)
    monkeypatch.setattr(
        openstack_manager,
        "_create_connection",
        MagicMock(spec=openstack_manager._create_connection, return_value=mock_connection),
    )
    return mock_connection.__enter__()


@pytest.fixture(name="ssh_connection_mock")
def ssh_connection_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Return a mocked ssh connection."""
    test_file_content = secrets.token_hex(16)
    ssh_conn_mock = MagicMock(spec=openstack_manager.SshConnection)
    ssh_conn_mock.get.side_effect = lambda remote, local: Path(local).write_text(test_file_content)
    ssh_conn_mock.run.side_effect = lambda cmd, **kwargs: (
        Result(stdout="1") if cmd.startswith("stat") else Result()
    )
    ssh_conn_mock.run.return_value = Result()

    return ssh_conn_mock


@pytest.fixture(name="openstack_manager_for_reconcile")
def openstack_manager_for_reconcile_fixture(
    monkeypatch: pytest.MonkeyPatch,
    mock_github_client: MagicMock,
    patched_create_connection_context: MagicMock,
    tmp_path: Path,
    ssh_connection_mock: MagicMock,
):
    """Create a mocked openstack manager for the reconcile tests."""
    t_mock = MagicMock(return_value=12345)
    monkeypatch.setattr(openstack_manager.time, "time", t_mock)

    issue_event_mock = MagicMock(spec=metric_events.issue_event)
    monkeypatch.setattr(openstack_manager.metric_events, "issue_event", issue_event_mock)

    runner_metrics_mock = MagicMock(openstack_manager.runner_metrics)
    monkeypatch.setattr(openstack_manager, "runner_metrics", runner_metrics_mock)

    github_metrics_mock = MagicMock(openstack_manager.github_metrics)
    monkeypatch.setattr(openstack_manager, "github_metrics", github_metrics_mock)

    monkeypatch.setattr(
        openstack_manager, "GithubClient", MagicMock(return_value=mock_github_client)
    )

    runner_metrics_path = tmp_path / "runner_fs"
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))
    monkeypatch.setattr(openstack_manager.metrics_storage, "get", MagicMock(return_value=ms))

    pool_mock = MagicMock()
    pool_mock.__enter__.return_value = pool_mock
    pool_mock.map.side_effect = lambda func, iterable: func(*iterable)
    pool_cls_mock = MagicMock()
    pool_cls_mock.return_value = pool_mock
    monkeypatch.setattr(openstack_manager, "Pool", pool_cls_mock)

    app_name = secrets.token_hex(16)
    charm_state = MagicMock(spec=CharmState)
    charm_state.proxy_config = ProxyConfig()
    charm_state.ssh_debug_connections = MagicMock()
    charm_state.charm_config = MagicMock()
    charm_state.charm_config.repo_policy_compliance = None
    os_runner_manager_config = openstack_manager.OpenstackRunnerManagerConfig(
        charm_state=charm_state,
        path=MagicMock(),
        labels=[],
        token=secrets.token_hex(16),
        flavor=app_name,
        image="test-image-id",
        network=secrets.token_hex(16),
        dockerhub_mirror=None,
    )
    patched_create_connection_context.create_keypair.return_value = Keypair(private_key="test_key")
    server_mock = MagicMock()
    server_mock.status = openstack_manager._INSTANCE_STATUS_ACTIVE
    patched_create_connection_context.get_server.return_value = server_mock

    os_runner_manager = openstack_manager.OpenstackRunnerManager(
        app_name=app_name,
        unit_num=0,
        openstack_runner_manager_config=os_runner_manager_config,
        cloud_config={},
    )
    os_runner_manager._ssh_health_check = MagicMock(return_value=True)
    os_runner_manager._get_ssh_connection = MagicMock(return_value=ssh_connection_mock)
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager, "_wait_until_runner_process_running", MagicMock()
    )

    monkeypatch.setattr(openstack_manager, "_SSH_KEY_PATH", tmp_path)
    monkeypatch.setattr(openstack_manager.shutil, "chown", MagicMock())

    return os_runner_manager


def test__create_connection_error(clouds_yaml: dict, openstack_connect_mock: MagicMock):
    """
    arrange: given a monkeypatched connection.authorize() function that raises an error.
    act: when _create_connection is called.
    assert: OpenStackUnauthorizedError is raised.
    """
    connection_mock = MagicMock()
    connection_context = MagicMock()
    connection_context.authorize.side_effect = openstack.exceptions.HttpException
    connection_mock.__enter__.return_value = connection_context
    openstack_connect_mock.return_value = connection_mock

    with pytest.raises(OpenStackError) as exc:
        with openstack_manager._create_connection(cloud_config=clouds_yaml):
            pass

    assert "Failed OpenStack API call" in str(exc)


def test__create_connection(
    multi_clouds_yaml: dict, clouds_yaml: dict, cloud_name: str, openstack_connect_mock: MagicMock
):
    """
    arrange: given a cloud config yaml dict with 1. multiple clouds 2. single cloud.
    act: when _create_connection is called.
    assert: connection with first cloud in the config is used.
    """
    # 1. multiple clouds
    with openstack_manager._create_connection(cloud_config=multi_clouds_yaml):
        openstack_connect_mock.assert_called_with(cloud=CLOUD_NAME)

    # 2. single cloud
    with openstack_manager._create_connection(cloud_config=clouds_yaml):
        openstack_connect_mock.assert_called_with(cloud=cloud_name)


@pytest.mark.parametrize(
    "proxy_config, dockerhub_mirror, ssh_debug_connections, expected_env_contents",
    [
        pytest.param(
            None,
            None,
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/ubuntu/actions-runner/pre-job.sh
""",
            id="all values empty",
        ),
        pytest.param(
            openstack_manager.ProxyConfig(
                http="http://test.internal",
                https="https://test.internal",
                no_proxy="http://no_proxy.internal",
            ),
            None,
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/ubuntu/actions-runner/pre-job.sh
""",
            id="proxy value set",
        ),
        pytest.param(
            None,
            "http://dockerhub_mirror.test",
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





DOCKERHUB_MIRROR=http://dockerhub_mirror.test
CONTAINER_REGISTRY_URL=http://dockerhub_mirror.test

LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/ubuntu/actions-runner/pre-job.sh
""",
            id="dockerhub mirror set",
        ),
        pytest.param(
            None,
            None,
            [
                openstack_manager.SSHDebugConnection(
                    host="127.0.0.1",
                    port=10022,
                    rsa_fingerprint="SHA256:testrsa",
                    ed25519_fingerprint="SHA256:tested25519",
                )
            ],
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/ubuntu/actions-runner/pre-job.sh

TMATE_SERVER_HOST=127.0.0.1
TMATE_SERVER_PORT=10022
TMATE_SERVER_RSA_FINGERPRINT=SHA256:testrsa
TMATE_SERVER_ED25519_FINGERPRINT=SHA256:tested25519
""",
            id="ssh debug connection set",
        ),
        pytest.param(
            openstack_manager.ProxyConfig(
                http="http://test.internal",
                https="https://test.internal",
                no_proxy="http://no_proxy.internal",
            ),
            "http://dockerhub_mirror.test",
            [
                openstack_manager.SSHDebugConnection(
                    host="127.0.0.1",
                    port=10022,
                    rsa_fingerprint="SHA256:testrsa",
                    ed25519_fingerprint="SHA256:tested25519",
                )
            ],
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





DOCKERHUB_MIRROR=http://dockerhub_mirror.test
CONTAINER_REGISTRY_URL=http://dockerhub_mirror.test

LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=/home/ubuntu/actions-runner/pre-job.sh

TMATE_SERVER_HOST=127.0.0.1
TMATE_SERVER_PORT=10022
TMATE_SERVER_RSA_FINGERPRINT=SHA256:testrsa
TMATE_SERVER_ED25519_FINGERPRINT=SHA256:tested25519
""",
            id="all values set",
        ),
    ],
)
def test__generate_runner_env(
    proxy_config: Optional[openstack_manager.ProxyConfig],
    dockerhub_mirror: Optional[str],
    ssh_debug_connections: Optional[list[openstack_manager.SSHDebugConnection]],
    expected_env_contents: str,
):
    """
    arrange: given configuration values for runner environment.
    act: when _generate_runner_env is called.
    assert: expected .env contents are generated.
    """
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)
    assert (
        openstack_manager._generate_runner_env(
            templates_env=environment,
            dockerhub_mirror=dockerhub_mirror,
            ssh_debug_connections=ssh_debug_connections,
        )
        == expected_env_contents
    )


def test_reconcile_issues_runner_installed_event(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
):
    """
    arrange: Mock openstack manager for reconcile.
    act: Reconcile to create a runner.
    assert: The expected event is issued.
    """
    openstack_manager_for_reconcile.reconcile(quantity=1)

    openstack_manager.metric_events.issue_event.assert_has_calls(
        [
            call(
                event=metric_events.RunnerInstalled(
                    timestamp=openstack_manager.time.time(),
                    flavor=openstack_manager_for_reconcile.app_name,
                    duration=0,
                )
            )
        ]
    )


def test_reconcile_places_timestamp_in_metrics_storage(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    arrange: Mock timestamps and create the directory for the metrics storage.
    act: Reconcile to create a runner.
    assert: The expected timestamp is placed in the shared filesystem.
    """
    runner_metrics_path = tmp_path / "runner_fs"
    runner_metrics_path.mkdir()
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))

    openstack_manager_for_reconcile.reconcile(quantity=1)

    assert (ms.path / RUNNER_INSTALLED_TS_FILE_NAME).exists()
    assert (ms.path / RUNNER_INSTALLED_TS_FILE_NAME).read_text() == str(
        openstack_manager.time.time()
    )


def test_reconcile_error_on_placing_timestamp_is_ignored(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    arrange: Do not create the directory for the metrics storage\
        in order to let a FileNotFoundError to be raised inside the OpenstackRunnerManager.
    act: Reconcile to create a runner.
    assert: No exception is raised.
    """
    runner_metrics_path = tmp_path / "runner_fs"

    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))

    openstack_manager_for_reconcile.reconcile(quantity=1)

    assert not (ms.path / RUNNER_INSTALLED_TS_FILE_NAME).exists()


def test_reconcile_pulls_metric_files(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ssh_connection_mock: MagicMock,
):
    """
    arrange: Mock the metrics storage and the ssh connection.
    act: Reconcile to create a runner.
    assert: The expected metric files are pulled from the shared filesystem.
    """
    runner_metrics_path = tmp_path / "runner_fs"
    runner_metrics_path.mkdir()
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))
    monkeypatch.setattr(openstack_manager.metrics_storage, "get", MagicMock(return_value=ms))
    openstack_manager_for_reconcile._get_openstack_runner_status = MagicMock(
        return_value=RunnerByHealth(healthy=(), unhealthy=("test_runner",))
    )
    ssh_connection_mock.get.side_effect = MagicMock()
    openstack_manager_for_reconcile.reconcile(quantity=0)

    ssh_connection_mock.get.assert_any_call(
        remote=str(METRICS_EXCHANGE_PATH / "pre-job-metrics.json"),
        local=str(ms.path / "pre-job-metrics.json"),
    )
    ssh_connection_mock.get.assert_any_call(
        remote=str(METRICS_EXCHANGE_PATH / "post-job-metrics.json"),
        local=str(ms.path / "post-job-metrics.json"),
    )


def test_reconcile_does_not_pull_too_large_files(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ssh_connection_mock: MagicMock,
):
    """
    arrange: Mock the metrics storage and the ssh connection to return a file that is too large.
    act: Reconcile to create a runner.
    assert: The expected metric files are not pulled from the shared filesystem.
    """
    runner_metrics_path = tmp_path / "runner_fs"
    runner_metrics_path.mkdir()
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))
    monkeypatch.setattr(openstack_manager.metrics_storage, "get", MagicMock(return_value=ms))
    ssh_connection_mock.run.side_effect = lambda cmd, **kwargs: (
        Result(stdout=f"{MAX_METRICS_FILE_SIZE + 1}") if cmd.startswith("stat") else Result()
    )
    openstack_manager_for_reconcile._get_openstack_runner_status = MagicMock(
        return_value=RunnerByHealth(healthy=("test_runner",), unhealthy=())
    )

    openstack_manager_for_reconcile.reconcile(quantity=0)

    assert not (ms.path / "pre-job-metrics.json").exists()
    assert not (ms.path / "post-job-metrics.json").exists()


def test_reconcile_issue_reconciliation_metrics(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    arrange: Mock the metrics storage and the ssh connection.
    act: Reconcile.
    assert: The expected reconciliation metrics are issued.
    """
    runner_metrics_path = tmp_path / "runner_fs"
    runner_metrics_path.mkdir()
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))
    monkeypatch.setattr(openstack_manager.metrics_storage, "get", MagicMock(return_value=ms))
    openstack_manager_for_reconcile._get_openstack_runner_status = MagicMock(
        return_value=RunnerByHealth(healthy=("test_runner",), unhealthy=())
    )

    openstack_manager.runner_metrics.extract.return_value = (MagicMock() for _ in range(2))
    openstack_manager.runner_metrics.issue_events.side_effect = [
        {metric_events.RunnerStart, metric_events.RunnerStop},
        {metric_events.RunnerStart},
    ]

    openstack_manager_for_reconcile._github.get_runner_github_info.return_value = [
        SelfHostedRunner(
            busy=False,
            id=1,
            labels=[],
            os="linux",
            name=f"{openstack_manager_for_reconcile.instance_name}-test_runner",
            status=GitHubRunnerStatus.ONLINE,
        )
    ]
    openstack_manager_for_reconcile.reconcile(quantity=0)

    openstack_manager.metric_events.issue_event.assert_has_calls(
        [
            call(
                event=metric_events.Reconciliation(
                    timestamp=12345,
                    flavor=openstack_manager_for_reconcile.app_name,
                    crashed_runners=1,
                    idle_runners=1,
                    duration=0,
                )
            )
        ]
    )


def test_reconcile_ignores_metrics_for_openstack_online_runners(
    openstack_manager_for_reconcile,
    monkeypatch,
    tmp_path,
    patched_create_connection_context: MagicMock,
):
    """
    arrange: Combination of runner status/github status and openstack status.
    act: Call reconcile.
    assert: All runners which have an instance on Openstack are ignored for metrics extraction.
    """
    runner_metrics_path = tmp_path / "runner_fs"
    runner_metrics_path.mkdir()
    ms = MetricsStorage(path=runner_metrics_path, runner_name="test_runner")
    monkeypatch.setattr(openstack_manager.metrics_storage, "create", MagicMock(return_value=ms))
    monkeypatch.setattr(openstack_manager.metrics_storage, "get", MagicMock(return_value=ms))
    instance_name = openstack_manager_for_reconcile.instance_name
    runner_names = {
        k: f"{instance_name}-{k}"
        for k in [
            "healthy_online",
            "healthy_offline",
            "unhealthy_online",
            "unhealthy_offline",
            "openstack_online_no_github_status",
            "github_online_no_openstack_status",
        ]
    }
    openstack_manager_for_reconcile._get_openstack_runner_status = MagicMock(
        return_value=RunnerByHealth(
            healthy=(runner_names["healthy_online"], runner_names["healthy_offline"]),
            unhealthy=(
                runner_names["unhealthy_online"],
                runner_names["unhealthy_offline"],
                runner_names["github_online_no_openstack_status"],
            ),
        )
    )
    openstack_manager_for_reconcile.get_github_runner_info = MagicMock(
        return_value=(
            RunnerGithubInfo(
                runner_name=runner_names["healthy_online"], runner_id=0, online=True, busy=True
            ),
            RunnerGithubInfo(
                runner_name=runner_names["unhealthy_online"], runner_id=1, online=True, busy=False
            ),
            RunnerGithubInfo(
                runner_name=runner_names["healthy_offline"], runner_id=2, online=False, busy=False
            ),
            RunnerGithubInfo(
                runner_name=runner_names["unhealthy_offline"],
                runner_id=3,
                online=False,
                busy=False,
            ),
            RunnerGithubInfo(
                runner_name=runner_names["github_online_no_openstack_status"],
                runner_id=4,
                online=True,
                busy=False,
            ),
        )
    )

    openstack_online_runner_names = [
        runner
        for (name, runner) in runner_names.items()
        if name != "github_online_no_openstack_status"
    ]
    openstack_instances = [
        openstack_manager.openstack.compute.v2.server.Server(
            name=runner_name, status=random.choice(("ACTIVE", "BUILD", "STOPPED"))
        )
        for runner_name in openstack_online_runner_names
    ]
    patched_create_connection_context.list_servers.return_value = openstack_instances

    openstack_manager.runner_metrics.extract.return_value = (MagicMock() for _ in range(1))
    openstack_manager.runner_metrics.issue_events.side_effect = [
        {metric_events.RunnerStart, metric_events.RunnerStop},
    ]

    openstack_manager_for_reconcile.reconcile(quantity=0)

    openstack_manager.runner_metrics.extract.assert_called_once_with(
        metrics_storage_manager=metrics.storage,
        ignore_runners=set(openstack_online_runner_names),
    )


def test_repo_policy_config(
    openstack_manager_for_reconcile: openstack_manager.OpenstackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    patched_create_connection_context: MagicMock,
):
    """
    arrange: Mock the repo policy compliance config.
    act: Reconcile to create a runner.
    assert: The expected url and one-time-token is present in the pre-job script in \
        the cloud-init data.
    """
    test_url = "http://test.url"
    token = secrets.token_hex(16)
    one_time_token = secrets.token_hex(16)
    openstack_manager_for_reconcile._config.charm_state.charm_config.repo_policy_compliance = (
        RepoPolicyComplianceConfig(url=test_url, token=token)
    )
    repo_policy_compliance_client_mock = MagicMock(
        spec=openstack_manager.RepoPolicyComplianceClient
    )
    repo_policy_compliance_client_mock.base_url = test_url
    repo_policy_compliance_client_mock.get_one_time_token.return_value = one_time_token
    repo_policy_compliance_cls_mock = MagicMock(return_value=repo_policy_compliance_client_mock)
    monkeypatch.setattr(
        openstack_manager, "RepoPolicyComplianceClient", repo_policy_compliance_cls_mock
    )

    openstack_manager_for_reconcile.reconcile(quantity=1)

    cloud_init_data_str = patched_create_connection_context.create_server.call_args[1]["userdata"]
    repo_policy_compliance_client_mock.get_one_time_token.assert_called_once()
    assert one_time_token in cloud_init_data_str
    assert test_url in cloud_init_data_str


def test__ensure_security_group_with_existing_rules():
    """
    arrange: Mock OpenStack connection with the security rules created.
    act: Run `_ensure_security_group`.
    assert: The security rules are not created again.
    """
    connection_mock = MagicMock(spec=openstack.connection.Connection)
    connection_mock.get_security_group.return_value = {
        "security_group_rules": [
            {"protocol": "icmp"},
            {"protocol": "tcp", "port_range_min": 22, "port_range_max": 22},
            {"protocol": "tcp", "port_range_min": 10022, "port_range_max": 10022},
        ]
    }

    openstack_manager.OpenstackRunnerManager._ensure_security_group(connection_mock)
    connection_mock.create_security_group_rule.assert_not_called()


def test__get_ssh_connection(
    monkeypatch,
    patch_get_ssh_connection_health_check,
    mock_server: MagicMock,
):
    """
    arrange: A server with SSH setup correctly.
    act: Get the SSH connections.
    assert: The SSH connections contains at least one connection.
    """
    # Patching the `_get_key_path` to get around the keyfile checks.
    mock__get_key_path = MagicMock(spec=openstack_manager.OpenstackRunnerManager._get_key_path)
    mock_key_path = MagicMock(spec=Path)
    mock_key_path.exists.return_value = True
    mock__get_key_path.return_value = mock_key_path
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager, "_get_key_path", mock__get_key_path
    )
    mock_connection = MagicMock(spec=openstack.connection.Connection)
    mock_connection.get_server.return_value = mock_server

    conn = openstack_manager.OpenstackRunnerManager._get_ssh_connection(
        mock_connection, mock_server.name
    )
    assert conn is not None


def test__ssh_health_check_success(
    mock_server: MagicMock,
):
    """
    arrange: A server with SSH correctly setup.
    act: Run health check on the server.
    assert: The health check passes.
    """
    mock_connection = MagicMock(spec=openstack.connection.Connection)
    mock_connection.get_server.return_value = mock_server
    assert openstack_manager.OpenstackRunnerManager._ssh_health_check(
        mock_connection, mock_server.name, False
    )


def test__ssh_health_check_no_key(mock_server: MagicMock):
    """
    arrange: A server with no key available.
    act: Run health check on the server.
    assert: The health check fails.
    """
    # Remove the mock SSH key.
    mock_server.key_name = None

    mock_connection = MagicMock(spec=openstack.connection.Connection)
    mock_connection.get_server.return_value = mock_server

    assert openstack_manager.OpenstackRunnerManager._ssh_health_check(
        mock_connection, mock_server.name, False
    )


def test__ssh_health_check_error(mock_server: MagicMock, patch_ssh_connection_error):
    """
    arrange: A server with error on SSH run.
    act: Run health check on the server.
    assert: The health check fails.
    """
    mock_connection = MagicMock(spec=openstack.connection.Connection)
    mock_connection.get_server.return_value = mock_server
    openstack_manager.OpenstackRunnerManager._ssh_health_check(
        mock_connection, mock_server.name, False
    )


def test__wait_until_runner_process_running_no_server():
    """
    arrange: No server existing on the OpenStack connection.
    act: Check if runner process is running.
    assert: RunnerStartError thrown.
    """
    mock_connection = MagicMock(spec=openstack.connection.Connection)
    mock_connection.get_server.return_value = None

    with pytest.raises(RunnerStartError):
        openstack_manager.OpenstackRunnerManager._wait_until_runner_process_running(
            mock_connection, "Non-existing-server"
        )


@pytest.mark.parametrize(
    "server",
    [
        pytest.param(None, id="no server"),
        pytest.param(factories.MockOpenstackServer(status="SHUTOFF"), id="shutoff"),
        pytest.param(factories.MockOpenstackServer(status="REBUILD"), id="not active/building"),
    ],
)
def test__health_check(server: factories.MockOpenstackServer | None):
    """
    arrange: given a mock openstack.get_server response.
    act: when _health_check is called.
    assert: False is returned, meaning unhealthy runner.
    """
    mock_get_server = MagicMock(return_value=server)
    mock_connection = MagicMock()
    mock_connection.get_server = mock_get_server

    assert not openstack_manager.OpenstackRunnerManager._health_check(
        conn=mock_connection, server_name="test"
    )


# The SSH health check will temporarily return True on failure for debugging purposes.
@pytest.mark.xfail
def test__ssh_health_check_connection_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _get_ssh_connection function that raises _SSHError.
    act: when _ssh_health_check is called.
    assert: False is returned, meaning unhealthy runner.
    """
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_ssh_connection",
        MagicMock(side_effect=openstack_manager._SSHError),
    )

    assert not openstack_manager.OpenstackRunnerManager._ssh_health_check(
        server=MagicMock(), startup=False
    )


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(factories.MockSSHRunResult(exited=1), id="ssh result not ok"),
        pytest.param(
            factories.MockSSHRunResult(exited=0, stdout=""),
            id="runner process not found in stdout",
        ),
        # This health check should fail but temporarily marking as passing for passive runner
        # deletion until we have more data.
        pytest.param(
            factories.MockSSHRunResult(exited=0, stdout="/home/ubuntu/actions-runner/run.sh"),
            id="startup process exists but no listener or worker process",
        ),
    ],
)
@pytest.mark.xfail
def test__ssh_health_check_unhealthy(
    monkeypatch: pytest.MonkeyPatch, result: factories.MockSSHRunResult
):
    """
    arrange: given unhealthy ssh responses.
    act: when _ssh_health_check is called.
    assert: False is returned, meaning unhealthy runner.
    """
    mock_ssh_connection = MagicMock()
    mock_ssh_connection.run = MagicMock(return_value=result)
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_ssh_connection",
        MagicMock(return_value=mock_ssh_connection),
    )

    assert not openstack_manager.OpenstackRunnerManager._ssh_health_check(
        server=MagicMock(), startup=False
    )


@pytest.mark.parametrize(
    "result, startup",
    [
        pytest.param(
            factories.MockSSHRunResult(
                exited=0, stdout="/home/ubuntu/actions-runner/run.sh\nRunner.Worker"
            ),
            False,
            id="runner process & workper process found",
        ),
        pytest.param(
            factories.MockSSHRunResult(
                exited=0, stdout="/home/ubuntu/actions-runner/run.sh\nRunner.Listener"
            ),
            False,
            id="runner process & listener process found",
        ),
        pytest.param(
            factories.MockSSHRunResult(exited=0, stdout="/home/ubuntu/actions-runner/run.sh"),
            True,
            id="runner process found for startup",
        ),
    ],
)
def test__ssh_health_check_healthy(
    monkeypatch: pytest.MonkeyPatch, result: factories.MockSSHRunResult, startup: bool
):
    """
    arrange: given healthy ssh response.
    act: when _ssh_health_check is called.
    assert: True is returned, meaning healthy runner.
    """
    mock_ssh_connection = MagicMock()
    mock_ssh_connection.run = MagicMock(return_value=result)
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_ssh_connection",
        MagicMock(return_value=mock_ssh_connection),
    )

    assert openstack_manager.OpenstackRunnerManager._ssh_health_check(
        conn=MagicMock(), server_name=MagicMock(), startup=startup
    )


@pytest.mark.usefixtures("skip_retry")
def test__get_ssh_connection_server_gone():
    """
    arrange: given a mock Openstack get_server function that returns None.
    act: when _get_ssh_connection is called.
    assert: _SSHError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.get_server.return_value = None

    with pytest.raises(openstack_manager._SSHError) as exc:
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )

    assert "Server gone while trying to get SSH connection" in str(exc.getrepr())


@pytest.mark.usefixtures("skip_retry")
def test__get_ssh_connection_no_server_key():
    """
    arrange: given a mock server instance with no key attached.
    act: when _get_ssh_connection is called.
    assert: _SSHError is raised.
    """
    mock_server = MagicMock()
    mock_server.key_name = None
    mock_connection = MagicMock()
    mock_connection.get_server.return_value = mock_server

    with pytest.raises(openstack_manager._SSHError) as exc:
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )

    assert "Unable to create SSH connection, no valid keypair found" in str(exc.getrepr())


@pytest.mark.usefixtures("skip_retry")
def test__get_ssh_connection_key_not_exists(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _get_key_path function that returns a non-existent path.
    act: when _get_ssh_connection is called.
    assert: _SSHError is raised.
    """
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_key_path",
        MagicMock(return_value=Path("does-not-exist")),
    )
    mock_connection = MagicMock()

    with pytest.raises(openstack_manager._SSHError) as exc:
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )

    assert "Missing keyfile for server" in str(exc.getrepr())


@pytest.mark.usefixtures("skip_retry")
def test__get_ssh_connection_server_no_addresses(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mock server instance with no server addresses.
    act: when _get_ssh_connection is called.
    assert: _SSHError is raised.
    """
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_key_path",
        MagicMock(return_value=Path(".")),
    )
    mock_server = MagicMock()
    mock_server.addresses = {}
    mock_connection = MagicMock()
    mock_connection.get_server.return_value = mock_server

    with pytest.raises(openstack_manager._SSHError) as exc:
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )

    assert "No addresses found for OpenStack server" in str(exc.getrepr())


@pytest.mark.usefixtures("skip_retry")
@pytest.mark.parametrize(
    "run",
    [
        pytest.param(MagicMock(side_effect=TimeoutError), id="timeout error"),
        pytest.param(
            MagicMock(return_value=factories.MockSSHRunResult(exited=1)), id="result not ok"
        ),
        pytest.param(
            MagicMock(return_value=factories.MockSSHRunResult(exited=0, stdout="")),
            id="empty response",
        ),
    ],
)
def test__get_ssh_connection_server_no_valid_connections(
    monkeypatch: pytest.MonkeyPatch, run: MagicMock
):
    """
    arrange: given a monkeypatched Connection instance that returns invalid connections.
    act: when _get_ssh_connection is called.
    assert: _SSHError is raised.
    """
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_key_path",
        MagicMock(return_value=Path(".")),
    )
    mock_server = MagicMock()
    mock_server.addresses = {"test": [{"addr": "test-address"}]}
    mock_connection = MagicMock()
    mock_connection.get_server.return_value = mock_server
    mock_ssh_connection = MagicMock()
    mock_ssh_connection.run = run
    monkeypatch.setattr(
        openstack_manager, "SshConnection", MagicMock(return_value=mock_ssh_connection)
    )

    with pytest.raises(openstack_manager._SSHError) as exc:
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )

    assert "No connectable SSH addresses found" in str(exc.getrepr())


@pytest.mark.usefixtures("skip_retry")
def test__get_ssh_connection_server(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched SSH connection instance.
    act: when _get_ssh_connection is called.
    assert: the SSH connection instance is returned.
    """
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager,
        "_get_key_path",
        MagicMock(return_value=Path(".")),
    )
    mock_server = MagicMock()
    mock_server.addresses = {"test": [{"addr": "test-address"}]}
    mock_connection = MagicMock()
    mock_connection.get_server.return_value = mock_server
    mock_ssh_connection = MagicMock()
    mock_ssh_connection.run = MagicMock(
        return_value=factories.MockSSHRunResult(exited=0, stdout="hello world")
    )
    monkeypatch.setattr(
        openstack_manager, "SshConnection", MagicMock(return_value=mock_ssh_connection)
    )

    assert (
        openstack_manager.OpenstackRunnerManager._get_ssh_connection(
            conn=mock_connection, server_name="test"
        )
        == mock_ssh_connection
    )
