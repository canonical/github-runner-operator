# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for unit-testing OpenStack runner manager."""
import logging
import secrets
from datetime import datetime
from typing import Iterable
from unittest.mock import ANY, MagicMock

import pytest

from github_runner_manager.configuration import ProxyConfig, SupportServiceConfig, UserInfo
from github_runner_manager.errors import OpenstackHealthCheckError
from github_runner_manager.manager.cloud_runner_manager import (
    CodeInformation,
    PostJobMetrics,
    PostJobStatus,
    PreJobMetrics,
    RunnerMetrics,
)
from github_runner_manager.manager.models import InstanceID, RunnerContext, RunnerMetadata
from github_runner_manager.metrics import runner
from github_runner_manager.metrics.runner import PullFileError
from github_runner_manager.openstack_cloud import health_checks, openstack_cloud
from github_runner_manager.openstack_cloud.constants import (
    POST_JOB_METRICS_FILE_NAME,
    PRE_JOB_METRICS_FILE_NAME,
    RUNNER_INSTALLED_TS_FILE_NAME,
)
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
)
from tests.unit.factories import openstack_factory

logger = logging.getLogger(__name__)

OPENSTACK_INSTANCE_PREFIX = "test"


@pytest.fixture(name="runner_manager")
def openstack_runner_manager_fixture(
    monkeypatch: pytest.MonkeyPatch, user_info: UserInfo
) -> OpenStackRunnerManager:
    """Mock required dependencies/configs and return an OpenStackRunnerManager instance."""
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.OpenstackCloud",
        MagicMock(),
    )

    service_config_mock = MagicMock(list(SupportServiceConfig.__fields__.keys()))
    service_config_mock.proxy_config = None
    service_config_mock.runner_proxy_config = None
    service_config_mock.use_aproxy = False
    service_config_mock.ssh_debug_connections = []
    service_config_mock.repo_policy_compliance = None
    config = OpenStackRunnerManagerConfig(
        prefix="test",
        credentials=MagicMock(),
        server_config=MagicMock(),
        service_config=service_config_mock,
    )

    return OpenStackRunnerManager(config=config, user=user_info)


@pytest.fixture(name="runner_metrics_mock")
def runner_metrics_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the runner_metrics module."""
    runner_metrics_mock = MagicMock(spec=runner)
    monkeypatch.setattr(runner, "pull_runner_metrics", runner_metrics_mock)
    return runner_metrics_mock


def test_create_runner_with_aproxy(
    runner_manager: OpenStackRunnerManager, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Prepare service config with aproxy enabled and a runner proxy config.
    act: Create a runner.
    assert: The cloud init in the runner should enable the aproxy with the proxy.
    """
    # Pending to pass service_config as a dependency instead of mocking it this way.
    service_config = runner_manager._config.service_config
    service_config.use_aproxy = True
    service_config.runner_proxy_config = ProxyConfig(http="http://proxy.example.com:3128")

    prefix = "test"
    agent_command = "agent"
    runner_context = RunnerContext(shell_run_script=agent_command)
    instance_id = InstanceID.build(prefix=prefix)
    metadata = RunnerMetadata()

    openstack_cloud = MagicMock(spec=OpenstackCloud)
    monkeypatch.setattr(runner_manager, "_openstack_cloud", openstack_cloud)

    runner_manager.create_runner(instance_id, metadata, runner_context)
    openstack_cloud.launch_instance.assert_called_once()
    assert (
        "snap set aproxy proxy=proxy.example.com:3128"
        in openstack_cloud.launch_instance.call_args.kwargs["cloud_init"]
    )


def test_create_runner_without_aproxy(
    runner_manager: OpenStackRunnerManager, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Prepare service config with aproxy disables and a runner proxy config.
    act: Create a runner.
    assert: The cloud init in the runner should not reference aproxy.
    """
    # Pending to pass service_config as a dependency instead of mocking it this way.
    service_config = runner_manager._config.service_config
    service_config.use_aproxy = False
    service_config.runner_proxy_config = ProxyConfig(http="http://proxy.example.com:3128")

    prefix = "test"
    agent_command = "agent"
    runner_context = RunnerContext(shell_run_script=agent_command)
    instance_id = InstanceID.build(prefix=prefix)
    metadata = RunnerMetadata()

    openstack_cloud = MagicMock(spec=OpenstackCloud)
    monkeypatch.setattr(runner_manager, "_openstack_cloud", openstack_cloud)

    runner_manager.create_runner(instance_id, metadata, runner_context)
    openstack_cloud.launch_instance.assert_called_once()
    assert "aproxy" not in openstack_cloud.launch_instance.call_args.kwargs["cloud_init"]


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


def _params_test_cleanup_extract_metrics():
    """Builds parametrized input for the test_cleanup_extract_metrics.

    The following values are returned:
    runner_installed_metrics,pre_job_metrics,post_job_metrics,result
    """
    openstack_created_at = datetime.strptime(
        openstack_factory.SERVER_CREATED_AT, "%Y-%m-%dT%H:%M:%SZ"
    ).timestamp()
    openstack_installed_at = openstack_created_at + 20
    pre_job_timestamp = openstack_installed_at + 20
    post_job_timestamp = openstack_installed_at + 20
    pre_job_metrics_str = f"""{{
    "timestamp": {pre_job_timestamp},
    "workflow": "Workflow Dispatch Tests",
    "workflow_run_id": "13831611664",
    "repository": "canonical/github-runner-operator",
    "event": "workflow_dispatch"
    }}"""
    post_job_metrics_str = f"""{{
    "timestamp": {post_job_timestamp}, "status": "normal", "status_info": {{"code" : "200"}}
    }}"""

    return [
        pytest.param(None, None, None, [], id="All None. No metrics returned."),
        pytest.param(
            "", None, None, [], id="Invalid runner-installed metrics. No metrics returned."
        ),
        pytest.param(
            str(openstack_installed_at),
            None,
            None,
            [
                RunnerMetrics(
                    instance_id=InstanceID(
                        prefix=OPENSTACK_INSTANCE_PREFIX, reactive=False, suffix="unhealthy"
                    ),
                    installation_start_timestamp=openstack_created_at,
                    installed_timestamp=openstack_installed_at,
                    metadata=RunnerMetadata(),
                ),
            ],
            id="Only installed_timestamp. Metric returned.",
        ),
        pytest.param(
            str(openstack_installed_at),
            pre_job_metrics_str,
            None,
            [
                RunnerMetrics(
                    instance_id=InstanceID(
                        prefix=OPENSTACK_INSTANCE_PREFIX, reactive=False, suffix="unhealthy"
                    ),
                    installation_start_timestamp=openstack_created_at,
                    installed_timestamp=openstack_installed_at,
                    pre_job=PreJobMetrics(
                        timestamp=pre_job_timestamp,
                        workflow="Workflow Dispatch Tests",
                        workflow_run_id="13831611664",
                        repository="canonical/github-runner-operator",
                        event="workflow_dispatch",
                    ),
                    metadata=RunnerMetadata(),
                ),
            ],
            id="installed_timestamp and pre_job_metrics. Metric returned.",
        ),
        pytest.param(
            str(openstack_installed_at),
            pre_job_metrics_str,
            post_job_metrics_str,
            [
                RunnerMetrics(
                    metadata=RunnerMetadata(),
                    instance_id=InstanceID(
                        prefix=OPENSTACK_INSTANCE_PREFIX, reactive=False, suffix="unhealthy"
                    ),
                    installation_start_timestamp=openstack_created_at,
                    installed_timestamp=openstack_installed_at,
                    pre_job=PreJobMetrics(
                        timestamp=pre_job_timestamp,
                        workflow="Workflow Dispatch Tests",
                        workflow_run_id="13831611664",
                        repository="canonical/github-runner-operator",
                        event="workflow_dispatch",
                    ),
                    post_job=PostJobMetrics(
                        timestamp=post_job_timestamp,
                        status=PostJobStatus.NORMAL,
                        status_info=CodeInformation(code=200),
                    ),
                ),
            ],
            id="installed_timestamp, pre_job_metrics and post_job_metrics. Metric returned",
        ),
    ]


@pytest.mark.parametrize(
    "runner_installed_metrics,pre_job_metrics,post_job_metrics,result",
    _params_test_cleanup_extract_metrics(),
)
def test_cleanup_extract_metrics(
    runner_manager: OpenStackRunnerManager,
    runner_installed_metrics: str | None,
    pre_job_metrics: str | None,
    post_job_metrics: str | None,
    result: Iterable[RunnerMetrics],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Given different values for values of metrics for a runner.
    act: Cleanup the runner for those metrics.
    assert: The expected RunnerMetrics object is obtained, or None if there should not be one.
    """
    ssh_pull_file_mock = MagicMock()
    monkeypatch.setattr(
        "github_runner_manager.metrics.runner.ssh_pull_file",
        ssh_pull_file_mock,
    )

    def _ssh_pull_file(remote_path, *args, **kwargs):
        """Get a file from the runner."""
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
