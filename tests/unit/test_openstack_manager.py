#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, call

import jinja2
import openstack.exceptions
import pytest
from invoke import Result
from openstack.compute.v2.keypair import Keypair

from charm_state import CharmState, ProxyConfig
from errors import OpenStackError
from github_type import GitHubRunnerStatus, SelfHostedRunner
from metrics import events as metric_events
from metrics.runner import RUNNER_INSTALLED_TS_FILE_NAME
from metrics.storage import MetricsStorage
from openstack_cloud import openstack_manager
from openstack_cloud.openstack_manager import MAX_METRICS_FILE_SIZE
from runner_type import RunnerByHealth

CLOUD_NAME = "microstack"


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack_connect_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    monkeypatch.setattr("openstack_cloud.openstack_manager.openstack.connect", mock_connect)

    return mock_connect


@pytest.fixture(name="mock_github_client")
def mock_github_client_fixture() -> MagicMock:
    """Mocked github client that returns runner application."""
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.return_value = openstack_manager.RunnerApplication(
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
    os_runner_manager._get_ssh_connections = MagicMock(
        return_value=(ssh_connection_mock for _ in range(10))
    )
    monkeypatch.setattr(
        openstack_manager.OpenstackRunnerManager, "_wait_until_runner_process_running", MagicMock()
    )

    monkeypatch.setattr(openstack_manager, "_SSH_KEY_PATH", tmp_path)

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
    "arch",
    [
        pytest.param("s390x", id="s390x"),
        pytest.param("riscv64", id="riscv64"),
        pytest.param("ppc64el", id="ppc64el"),
        pytest.param("armhf", id="armhf"),
        pytest.param("test", id="test"),
    ],
)
def test__get_supported_runner_arch_invalid_arch(arch: str):
    """
    arrange: given supported architectures.
    act: when _get_supported_runner_arch is called.
    assert: supported cloud image architecture type is returned.
    """
    with pytest.raises(openstack_manager.UnsupportedArchitectureError) as exc:
        openstack_manager._get_supported_runner_arch(arch=arch)

    assert arch in str(exc)


@pytest.mark.parametrize(
    "arch, image_arch",
    [
        pytest.param("x64", "amd64", id="x64"),
        pytest.param("arm64", "arm64", id="arm64"),
    ],
)
def test__get_supported_runner_arch(arch: str, image_arch: str):
    """
    arrange: given supported architectures.
    act: when _get_supported_runner_arch is called.
    assert: supported cloud image architecture type is returned.
    """
    assert openstack_manager._get_supported_runner_arch(arch=arch) == image_arch


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


def test__build_image_command():
    """
    arrange: given a mock Github runner application and proxy config.
    act: when _build_image_command is called.
    assert: command for build image bash script with args are returned.
    """
    test_runner_info = openstack_manager.RunnerApplication(
        os="linux",
        architecture="x64",
        download_url=(test_download_url := "https://testdownloadurl.com"),
        filename="test_filename",
        temp_download_token=secrets.token_hex(16),
    )
    test_proxy_config = openstack_manager.ProxyConfig(
        http=(test_http_proxy := "http://proxy.test"),
        https=(test_https_proxy := "https://proxy.test"),
        no_proxy=(test_no_proxy := "http://no.proxy"),
        use_aproxy=False,
    )

    command = openstack_manager._build_image_command(
        runner_info=test_runner_info, proxies=test_proxy_config
    )
    assert command == [
        "/usr/bin/bash",
        openstack_manager.BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME,
        test_download_url,
        test_http_proxy,
        test_https_proxy,
        test_no_proxy,
    ], "Unexpected build image command."


def test_build_image_runner_binary_error():
    """
    arrange: given a mocked github client get_runner_application function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.side_effect = openstack_manager.RunnerBinaryError

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            arch=openstack_manager.Arch.X64,
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
        )

    assert "Failed to fetch runner application." in str(exc)


def test_build_image_script_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched execute_command function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(
            side_effect=openstack_manager.SubprocessError(
                cmd=[], return_code=1, stdout="", stderr=""
            )
        ),
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            arch=openstack_manager.Arch.X64,
            cloud_config=MagicMock(),
            github_client=MagicMock(),
            path=MagicMock(),
        )

    assert "Failed to build image." in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_runner_arch_error(
    monkeypatch: pytest.MonkeyPatch, mock_github_client: MagicMock
):
    """
    arrange: given _get_supported_runner_arch that raises unsupported architecture error.
    act: when build_image is called.
    assert: ImageBuildError error is raised with unsupported arch message.
    """
    mock_get_supported_runner_arch = MagicMock(
        spec=openstack_manager._get_supported_runner_arch,
        side_effect=openstack_manager.UnsupportedArchitectureError(arch="x64"),
    )
    monkeypatch.setattr(
        openstack_manager, "_get_supported_runner_arch", mock_get_supported_runner_arch
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            arch=openstack_manager.Arch.X64,
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
        )

    assert "Unsupported architecture" in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_delete_image_error(
    mock_github_client: MagicMock, patched_create_connection_context: MagicMock
):
    """
    arrange: given a mocked openstack connection that returns existing images and delete_image \
        that returns False (failed to delete image).
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    patched_create_connection_context.search_images.return_value = (
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
    )
    patched_create_connection_context.delete_image.return_value = False

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            arch=openstack_manager.Arch.X64,
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
        )

    assert "Failed to delete duplicate image on Openstack." in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_create_image_error(
    patched_create_connection_context: MagicMock, mock_github_client: MagicMock
):
    """
    arrange: given a mocked connection that raises OpenStackCloudException on create_image.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    patched_create_connection_context.create_image.side_effect = (
        openstack_manager.OpenStackCloudException
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            arch=openstack_manager.Arch.X64,
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
            proxies=None,
        )

    assert "Failed to update image" in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image(patched_create_connection_context: MagicMock, mock_github_client: MagicMock):
    """
    arrange: given monkeypatched execute_command and mocked openstack connection.
    act: when build_image is called.
    assert: Openstack image is successfully created.
    """
    patched_create_connection_context.search_images.return_value = (
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
    )

    openstack_manager.build_image(
        arch=openstack_manager.Arch.X64,
        cloud_config=MagicMock(),
        github_client=mock_github_client,
        path=MagicMock(),
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
        return_value=RunnerByHealth(healthy=("test_runner",), unhealthy=())
    )
    test_file_content = secrets.token_hex(16)
    ssh_connection_mock.get.side_effect = lambda remote, local: Path(local).write_text(
        test_file_content
    )

    openstack_manager_for_reconcile.reconcile(quantity=0)

    assert (ms.path / "pre-job-metrics.json").exists()
    assert (ms.path / "pre-job-metrics.json").read_text() == test_file_content
    assert (ms.path / "post-job-metrics.json").exists()
    assert (ms.path / "post-job-metrics.json").read_text() == test_file_content


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
    act: Reconcile to create a runner.
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
