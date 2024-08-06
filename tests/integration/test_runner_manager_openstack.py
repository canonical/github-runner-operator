# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing the RunnerManager class with OpenStackRunnerManager as CloudManager."""


from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from openstack.connection import Connection as OpenstackConnection

from charm_state import GithubPath, ProxyConfig, parse_github_path
from manager.cloud_runner_manager import CloudRunnerState
from manager.github_runner_manager import GithubRunnerState
from manager.runner_manager import FlushMode, RunnerManager, RunnerManagerConfig
from metrics import events, runner_logs
from openstack_cloud.openstack_cloud import _CLOUDS_YAML_PATH
from openstack_cloud.openstack_runner_manager import (
    OpenstackRunnerManager,
    OpenstackRunnerManagerConfig,
)
from tests.integration.helpers.openstack import PrivateEndpointConfigs


@pytest.fixture(scope="module", name="log_dir_base_path")
def log_dir_base_path_fixture(tmp_path_factory: Path):
    """Mock the log directory path and return it."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        runner_log_dir_path = tmp_path_factory.mktemp("log") / "runner_log"
        metric_log_path = tmp_path_factory.mktemp("log") / "runner_log"
        monkeypatch.setattr(runner_logs, "RUNNER_LOGS_DIR_PATH", runner_log_dir_path)
        monkeypatch.setattr(events, "METRICS_LOG_PATH", metric_log_path)
        yield


@pytest.fixture(scope="module", name="github_path")
def github_path_fixture(path: str) -> GithubPath:
    return parse_github_path(path, "Default")


@pytest.fixture(scope="module", name="proxy_config")
def openstack_proxy_config_fixture(
    openstack_http_proxy: str, openstack_https_proxy: str, openstack_no_proxy: str
) -> ProxyConfig:
    use_aproxy = False
    if openstack_http_proxy or openstack_https_proxy:
        use_aproxy = True
    openstack_http_proxy = openstack_http_proxy if openstack_http_proxy else None
    openstack_https_proxy = openstack_https_proxy if openstack_https_proxy else None
    return ProxyConfig(
        http=openstack_http_proxy,
        https=openstack_https_proxy,
        no_proxy=openstack_no_proxy,
        use_aproxy=use_aproxy,
    )


@pytest_asyncio.fixture(scope="module", name="openstack_runner_manager")
async def openstack_runner_manager_fixture(
    app_name: str,
    private_endpoint_clouds_yaml: str,
    openstack_test_image: str,
    flavor_name: str,
    network_name: str,
    github_path: GithubPath,
    proxy_config: ProxyConfig,
    openstack_connection: OpenstackConnection,
) -> OpenstackRunnerManager:
    """Create OpenstackRunnerManager instance.

    The prefix args of OpenstackRunnerManager set to app_name to let openstack_connection_fixture preform the cleanup of openstack resources.
    """
    _CLOUDS_YAML_PATH.unlink(missing_ok=True)
    clouds_config = yaml.safe_load(private_endpoint_clouds_yaml)

    config = OpenstackRunnerManagerConfig(
        clouds_config=clouds_config,
        cloud="testcloud",
        image=openstack_test_image,
        flavor=flavor_name,
        network=network_name,
        github_path=github_path,
        labels=["openstack_test"],
        proxy_config=proxy_config,
        dockerhub_mirror=None,
        ssh_debug_connections=None,
        repo_policy_url=None,
        repo_policy_token=None,
    )
    return OpenstackRunnerManager(app_name, config)


@pytest_asyncio.fixture(scope="module", name="runner_manager")
async def runner_manager_fixture(
    openstack_runner_manager: OpenstackRunnerManager,
    token: str,
    github_path: GithubPath,
    log_dir_base_path: Path,
) -> RunnerManager:
    """Get RunnerManager instance.

    Import of log_dir_base_path to monkeypatch the runner logs path with tmp_path.
    """
    config = RunnerManagerConfig(token, github_path)
    return RunnerManager(openstack_runner_manager, config)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_get_no_runner(runner_manager: RunnerManager) -> None:
    """
    Arrange: RunnerManager instance with no runners.
    Act: Get runners.
    Assert: Empty tuple returned.
    """
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert not runner_list


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_runner_normal_idle_lifecycle(
    runner_manager: RunnerManager, openstack_runner_manager: OpenstackRunnerManager
) -> None:
    """
    Arrange: RunnerManager instance with no runners.
    Act:
        1. Create one runner.
        2. Run health check on the runner.
        4. Delete all busy runner.
        4. Delete all idle runner.
    Assert:
        1. An active idle runner.
        2. Health check passes.
        3. An active idle runner.
        4. No runners.
    """
    # 1.
    runner_id_list = runner_manager.create_runners(1)
    assert isinstance(runner_id_list, tuple)
    assert len(runner_id_list) == 1
    runner_id = runner_id_list[0]

    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 1
    runner = runner_list[0]
    assert runner.id == runner_id
    assert runner.cloud_state == CloudRunnerState.ACTIVE
    assert runner.github_state == GithubRunnerState.IDLE

    # 2.
    openstack_instances = openstack_runner_manager._openstack_cloud.get_instances()
    assert len(openstack_instances) == 1, "Test arrange failed: Needs one runner."
    runner = openstack_instances[0]

    assert openstack_runner_manager._health_check(runner)

    # TODO: debug
    pytest.set_trace()

    # 3.
    runner_manager.delete_runners(flush_mode=FlushMode.FLUSH_BUSY)
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 1
    runner = runner_list[0]
    assert runner.id == runner_id
    assert runner.cloud_state == CloudRunnerState.ACTIVE
    assert runner.github_state == GithubRunnerState.IDLE

    # 4.
    runner_manager.delete_runners(flush_mode=FlushMode.FLUSH_IDLE)
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 0


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_runner_normal_busy_lifecycle(
    runner_manager: RunnerManager, openstack_runner_manager: OpenstackRunnerManager
):
    pass
