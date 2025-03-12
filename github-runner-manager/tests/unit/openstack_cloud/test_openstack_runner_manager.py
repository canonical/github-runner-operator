# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for unit-testing OpenStack runner manager."""
import logging
import secrets
from typing import Optional, Iterable
from unittest.mock import ANY, MagicMock

import pytest
from fabric import Connection as SSHConnection
from invoke.runners import Result

from github_runner_manager.configuration import SupportServiceConfig
from github_runner_manager.errors import OpenstackHealthCheckError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.metrics import runner
from github_runner_manager.metrics.runner import RunnerMetrics
from github_runner_manager.openstack_cloud import (
    health_checks,
    openstack_cloud,
    openstack_runner_manager,
)
from github_runner_manager.openstack_cloud.constants import (
    POST_JOB_METRICS_FILE_NAME,
    PRE_JOB_METRICS_FILE_NAME,
    RUNNER_INSTALLED_TS_FILE_NAME,
)
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
    PullFileError,
    ssh_pull_file,
)
from tests.unit.factories import openstack_factory

logger = logging.getLogger(__name__)

OPENSTACK_INSTANCE_PREFIX = "test"


@pytest.fixture(name="runner_manager")
def openstack_runner_manager_fixture(monkeypatch: pytest.MonkeyPatch) -> OpenStackRunnerManager:
    """Mock required dependencies/configs and return an OpenStackRunnerManager instance."""
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.OpenstackCloud",
        MagicMock(),
    )

    service_config_mock = MagicMock(spec=SupportServiceConfig)
    service_config_mock.proxy_config = None
    config = OpenStackRunnerManagerConfig(
        prefix="test",
        credentials=MagicMock(),
        server_config=MagicMock(),
        service_config=service_config_mock,
    )

    return OpenStackRunnerManager(config=config)


@pytest.fixture(name="runner_metrics_mock")
def runner_metrics_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the runner_metrics module."""
    runner_metrics_mock = MagicMock(spec=runner)
    monkeypatch.setattr(openstack_runner_manager, "pull_runner_metrics", runner_metrics_mock)
    return runner_metrics_mock


@pytest.mark.parametrize(
    "healthy_count, unhealthy_count, unknown_count",
    [
        pytest.param(1, 1, 1, id="one of each"),
        pytest.param(2, 1, 1, id="two healthy"),
        pytest.param(1, 2, 1, id="two unhealthy"),
        pytest.param(1, 1, 2, id="two unknown"),
        pytest.param(0, 0, 0, id="no runners"),
        pytest.param(0, 0, 1, id="one unknown"),
        pytest.param(0, 1, 0, id="one unhealthy"),
        pytest.param(1, 0, 0, id="one healthy"),
    ],
)
def test_cleanup_ignores_runners_with_health_check_errors(
    healthy_count: int,
    unhealthy_count: int,
    unknown_count,
    monkeypatch: pytest.MonkeyPatch,
    runner_manager: OpenStackRunnerManager,
    runner_metrics_mock: MagicMock,
):
    """
    arrange: Given a combination of healthy/unhealthy/unknown(with a health check error) runners.
    act: When the cleanup method is called.
    assert: Only the unhealthy runners are deleted and their metrics are extracted.
    """
    prefix = "test"
    names = [
        InstanceID(prefix=prefix, reactive=False, suffix=f"{status}{i}").name
        for status, count in [
            ("healthy", healthy_count),
            ("unhealthy", unhealthy_count),
            (
                "unknown",
                unknown_count,
            ),
        ]
        for i in range(count)
    ]
    openstack_cloud_mock = _create_openstack_cloud_mock(names)
    runner_manager._openstack_cloud = openstack_cloud_mock
    health_checks_mock = _create_health_checks_mock()
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.health_checks",
        health_checks_mock,
    )
    runner_manager.cleanup(secrets.token_hex(16))

    assert openstack_cloud_mock.delete_instance.call_count == unhealthy_count
    for name in names:
        instance_id = name
        if instance_id.startswith("unhealthy"):
            openstack_cloud_mock.delete_instance.assert_any_call(instance_id)
    unhealthy_ids = {
        InstanceID.build_from_name(prefix, name) for name in names if "unhealthy" in name
    }
    assert runner_metrics_mock.call_count == len(unhealthy_ids)
    for unhealthy_id in unhealthy_ids:
        runner_metrics_mock.assert_any_call(unhealthy_id, ANY)


@pytest.mark.parametrize(
    "runner_installed_metrics,pre_job_metrics,post_job_metrics,result",
    [
        pytest.param(None, None, None, [], id="All None"),
        pytest.param("TODO THIS ANS MORE TESTS", None, None, [
            RunnerMetrics(
                instance_id=InstanceID(prefix=OPENSTACK_INSTANCE_PREFIX, reactive=False, suffix="unhealthy"),
                installed_timestamp=55,
            ),
        ], id="All None"),
    ],
)
def test_cleanup_extract_metrics(
    runner_manager: OpenStackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
    runner_installed_metrics: str | None,
    pre_job_metrics: str | None,
    post_job_metrics: str | None,
    result: Iterable[RunnerMetrics]
):
    """
    arrange: Given different combinations of healthy, unhealthy and undecided runners.
    act: When the cleanup method is called.
    assert: runner_metrics.extract is called with the expected storage to be extracted.
    """
    # created at is hardcoded to "2024-09-12T02:48:03Z" for all openstack instances.

    ssh_pull_file_mock = MagicMock()
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.ssh_pull_file",
        ssh_pull_file_mock,
    )

    def _ssh_pull_file(remote_path, *args, **kwargs):
        """TODO."""
        logger.info("ssh_pull_file: remote_path %s", remote_path)
        res = None
        if remote_path == str(PRE_JOB_METRICS_FILE_NAME):
            res = pre_job_metrics
        elif remote_path == str(POST_JOB_METRICS_FILE_NAME):
            res = post_job_metrics
        elif remote_path == str(RUNNER_INSTALLED_TS_FILE_NAME):
            res = runner_installed_metrics
        if res is None:
            raise PullFileError("Nothing found or invalid file.")
        return res

    ssh_pull_file_mock.side_effect = _ssh_pull_file

    names = [InstanceID(prefix=OPENSTACK_INSTANCE_PREFIX, reactive=False, suffix="unhealthy").name]
    openstack_cloud_mock = _create_openstack_cloud_mock(names)
    runner_manager._openstack_cloud = openstack_cloud_mock
    health_checks_mock = _create_health_checks_mock()
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.health_checks",
        health_checks_mock,
    )

    runner_metrics = runner_manager.cleanup("remove_token")
    assert runner_metrics == result


def test_ssh_pull_file():
    """
    arrange: TODO.
    act: TODO.
    assert: TODO.
    """
    remote_path = "/var/whatever"
    max_size = 100
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """TODO."""
        assert "stat" in command
        assert remote_path in command
        file_size = 10
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    def _ssh_get(remote, local) -> None:
        """TODO."""
        assert remote_path in remote
        local.write(b"content from")
        local.write(b" the file")
        return None

    ssh_conn.get.side_effect = _ssh_get

    response = ssh_pull_file(ssh_conn, remote_path, max_size)
    assert response == "content from the file"


def test_ssh_pull_file_invalid_size_real():
    """
    arrange: TODO.
    act: TODO.
    assert: TODO.
    """
    remote_path = "/var/whatever"
    max_size = 10
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """TODO."""
        assert "stat" in command
        assert remote_path in command
        file_size = 5
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    def _ssh_get(remote, local) -> None:
        """TODO."""
        assert remote_path in remote
        local.write(b"content")
        local.write(b"more content")
        return None

    ssh_conn.get.side_effect = _ssh_get

    with pytest.raises(PullFileError) as exc:
        _ = ssh_pull_file(ssh_conn, remote_path, max_size)
        assert "max" in str(exc)


def test_ssh_pull_file_invalid_size_reported():
    """
    arrange: TODO.
    act: TODO.
    assert: TODO.
    """
    remote_path = "/var/whatever"
    max_size = 10
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """TODO."""
        assert "stat" in command
        assert remote_path in command
        file_size = 20
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    with pytest.raises(PullFileError) as exc:
        _ = ssh_pull_file(ssh_conn, remote_path, max_size)
    assert "too large" in str(exc)


def _create_openstack_cloud_mock(server_names: list[str]) -> MagicMock:
    """Create an OpenstackCloud mock which returns servers with a given list of server names."""
    openstack_cloud_mock = MagicMock(spec=OpenstackCloud)
    openstack_cloud_mock.get_instances.return_value = [
        openstack_cloud.OpenstackInstance(
            server=openstack_factory.ServerFactory(
                status="ACTIVE",
                name=name,
            ),
            prefix=OPENSTACK_INSTANCE_PREFIX,
        )
        for name in server_names
    ]
    return openstack_cloud_mock


def _create_health_checks_mock() -> MagicMock:
    """Create a health check mock that returns a boolean or raises an error.

    The logic is that if the server name starts with "test-healthy" it returns True,
    if it starts with "test-unhealthy" it returns False, and raises an error otherwise.
    """
    health_checks_mock = MagicMock(spec=health_checks)

    def _health_checks_side_effect(openstack_cloud, instance):
        """Mock side effect for the health_checks.check_runner method.

        This implements the logic mentioned in the docstring above.
        """
        if instance.instance_id.prefix == "test" and instance.instance_id.suffix.startswith(
            "healthy"
        ):
            return True
        if instance.instance_id.prefix == "test" and instance.instance_id.suffix.startswith(
            "unhealthy"
        ):
            return False
        raise OpenstackHealthCheckError("Health check failed")

    health_checks_mock.check_runner.side_effect = _health_checks_side_effect
    return health_checks_mock
