# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing the RunnerManager class with OpenStackRunnerManager as CloudManager."""


import json
from pathlib import Path
from secrets import token_hex
from typing import Iterator

import pytest
import pytest_asyncio
import yaml
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from openstack.connection import Connection as OpenstackConnection

from charm_state import GitHubPath, ProxyConfig, parse_github_path
from manager.cloud_runner_manager import CloudRunnerState, GitHubRunnerConfig, SupportServiceConfig
from manager.github_runner_manager import GitHubRunnerState
from manager.runner_manager import FlushMode, RunnerManager, RunnerManagerConfig
from metrics import events, storage
from openstack_cloud.openstack_cloud import _CLOUDS_YAML_PATH
from openstack_cloud.openstack_runner_manager import (
    OpenStackCloudConfig,
    OpenStackRunnerManager,
    OpenStackServerConfig,
)
from tests.integration.helpers.common import (
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    wait_for,
)


@pytest.fixture(scope="module", name="runner_label")
def runner_label():
    return f"test-{token_hex(6)}"


@pytest.fixture(scope="module", name="log_dir_base_path")
def log_dir_base_path_fixture(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[dict[str, Path]]:
    """Mock the log directory path and return it."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        temp_log_dir = tmp_path_factory.mktemp("log")

        filesystem_base_path = temp_log_dir / "runner-fs"
        filesystem_quarantine_path = temp_log_dir / "runner-fs-quarantine"
        metric_log_path = temp_log_dir / "metric_log"

        monkeypatch.setattr(storage, "FILESYSTEM_BASE_PATH", filesystem_base_path)
        monkeypatch.setattr(storage, "FILESYSTEM_QUARANTINE_PATH", filesystem_quarantine_path)
        monkeypatch.setattr(events, "METRICS_LOG_PATH", metric_log_path)

        yield {
            "filesystem_base_path": filesystem_base_path,
            "filesystem_quarantine_path": filesystem_quarantine_path,
            "metric_log": metric_log_path,
        }


@pytest.fixture(scope="module", name="github_path")
def github_path_fixture(path: str) -> GitHubPath:
    return parse_github_path(path, "Default")


@pytest.fixture(scope="module", name="proxy_config")
def openstack_proxy_config_fixture(
    openstack_http_proxy: str, openstack_https_proxy: str, openstack_no_proxy: str
) -> ProxyConfig:
    use_aproxy = False
    if openstack_http_proxy or openstack_https_proxy:
        use_aproxy = True
    http_proxy = openstack_http_proxy if openstack_http_proxy else None
    https_proxy = openstack_https_proxy if openstack_https_proxy else None
    return ProxyConfig(
        http=http_proxy,
        https=https_proxy,
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
    github_path: GitHubPath,
    proxy_config: ProxyConfig,
    runner_label: str,
    openstack_connection: OpenstackConnection,
) -> OpenStackRunnerManager:
    """Create OpenstackRunnerManager instance.

    The prefix args of OpenstackRunnerManager set to app_name to let openstack_connection_fixture
    perform the cleanup of openstack resources.
    """
    _CLOUDS_YAML_PATH.unlink(missing_ok=True)
    clouds_config = yaml.safe_load(private_endpoint_clouds_yaml)

    cloud_config = OpenStackCloudConfig(
        clouds_config=clouds_config,
        cloud="testcloud",
    )
    server_config = OpenStackServerConfig(
        image=openstack_test_image,
        flavor=flavor_name,
        network=network_name,
    )
    runner_config = GitHubRunnerConfig(
        github_path=github_path,
        labels=["openstack_test", runner_label],
    )
    service_config = SupportServiceConfig(
        proxy_config=proxy_config,
        dockerhub_mirror=None,
        ssh_debug_connections=None,
        repo_policy_compliance=None,
    )
    return OpenStackRunnerManager(
        app_name, cloud_config, server_config, runner_config, service_config
    )


@pytest_asyncio.fixture(scope="module", name="runner_manager")
async def runner_manager_fixture(
    openstack_runner_manager: OpenStackRunnerManager,
    token: str,
    github_path: GitHubPath,
    log_dir_base_path: dict[str, Path],
) -> RunnerManager:
    """Get RunnerManager instance.

    Import of log_dir_base_path to monkeypatch the runner logs path with tmp_path.
    """
    config = RunnerManagerConfig(token, github_path)
    return RunnerManager(openstack_runner_manager, config)


@pytest_asyncio.fixture(scope="function", name="runner_manager_with_one_runner")
async def runner_manager_with_one_runner_fixture(runner_manager: RunnerManager) -> RunnerManager:
    runner_manager.create_runners(1)
    runner_list = runner_manager.get_runners()
    try:
        await wait_runner_amount(runner_manager, 1)
    except TimeoutError as err:
        raise AssertionError("Test arrange failed: Expect one runner") from err

    runner = runner_list[0]
    assert (
        runner.cloud_state == CloudRunnerState.ACTIVE
    ), "Test arrange failed: Expect runner in active state"
    try:
        await wait_for(
            lambda: runner_manager.get_runners()[0].github_state == GitHubRunnerState.IDLE,
            timeout=120,
            check_interval=10,
        )
    except TimeoutError as err:
        raise AssertionError("Test arrange failed: Expect runner in idle state") from err
    return runner_manager


def workflow_is_status(workflow: Workflow, status: str) -> bool:
    """Check if workflow in provided status.

    Args:
        workflow: The workflow to check.
        status: The status to check for.

    Returns:
        Whether the workflow is in the status.
    """
    workflow.update()
    return workflow.status == status


async def wait_runner_amount(runner_manager: RunnerManager, num: int):
    """Wait until the runner manager has the number of runners.

    A TimeoutError will be thrown if runners amount is not correct after timeout.

    Args:
        runner_manager: The RunnerManager to check.
        num: Number of runner to check for.
    """
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    if len(runner_list) == num:
        return

    # The openstack server can take sometime to fully clean up or create.
    await wait_for(lambda: len(runner_manager.get_runners()) == num)


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
    runner_manager: RunnerManager, openstack_runner_manager: OpenStackRunnerManager
) -> None:
    """
    Arrange: RunnerManager instance with no runners.
    Act:
        1. Create one runner.
        2. Run health check on the runner.
        3. Run cleanup.
        4. Delete all idle runner.
    Assert:
        1. An active idle runner.
        2. Health check passes.
        3. One idle runner remains.
        4. No runners.
    """
    # 1.
    runner_id_list = runner_manager.create_runners(1)
    assert isinstance(runner_id_list, tuple)
    assert len(runner_id_list) == 1
    runner_id = runner_id_list[0]

    try:
        await wait_runner_amount(runner_manager, 1)
    except TimeoutError as err:
        raise AssertionError("Test arrange failed: Expect one runner") from err

    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 1
    runner = runner_list[0]
    assert runner.instance_id == runner_id
    assert runner.cloud_state == CloudRunnerState.ACTIVE
    # Update on GitHub-side can take a bit of time.
    await wait_for(
        lambda: runner_manager.get_runners()[0].github_state == GitHubRunnerState.IDLE,
        timeout=120,
        check_interval=10,
    )

    # 2.
    openstack_instances = openstack_runner_manager._openstack_cloud.get_instances()
    assert len(openstack_instances) == 1, "Test arrange failed: Needs one runner."
    runner = openstack_instances[0]

    assert openstack_runner_manager._health_check(runner)

    # 3.
    runner_manager.cleanup()
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 1
    runner = runner_list[0]
    assert runner.instance_id == runner_id
    assert runner.cloud_state == CloudRunnerState.ACTIVE

    # 4.
    runner_manager.flush_runners(flush_mode=FlushMode.FLUSH_IDLE)
    await wait_runner_amount(runner_manager, 0)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_runner_flush_busy_lifecycle(
    runner_manager_with_one_runner: RunnerManager,
    test_github_branch: Branch,
    github_repository: Repository,
    runner_label: str,
):
    """
    Arrange: RunnerManager with one idle runner.
    Act:
        1. Run a long workflow.
        3. Run flush idle runner.
        4. Run flush busy runner.
    Assert:
        1. Runner takes the job and become busy.
        3. Busy runner still exists.
        4. No runners exists.
    """
    # 1.
    workflow = await dispatch_workflow(
        app=None,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": runner_label, "minutes": "30"},
        wait=False,
    )
    await wait_for(lambda: workflow_is_status(workflow, "in_progress"))

    runner_list = runner_manager_with_one_runner.get_runners()
    assert len(runner_list) == 1
    busy_runner = runner_list[0]
    assert busy_runner.cloud_state == CloudRunnerState.ACTIVE
    assert busy_runner.github_state == GitHubRunnerState.BUSY

    # 2.
    runner_manager_with_one_runner.cleanup()
    runner_list = runner_manager_with_one_runner.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 1
    runner = runner_list[0]
    assert runner.cloud_state == CloudRunnerState.ACTIVE
    assert busy_runner.github_state == GitHubRunnerState.BUSY

    # 3.
    runner_manager_with_one_runner.flush_runners(flush_mode=FlushMode.FLUSH_IDLE)
    runner_list = runner_manager_with_one_runner.get_runners()
    assert len(runner_list) == 1
    busy_runner = runner_list[0]
    assert busy_runner.cloud_state == CloudRunnerState.ACTIVE
    assert busy_runner.github_state == GitHubRunnerState.BUSY

    # 4.
    runner_manager_with_one_runner.flush_runners(flush_mode=FlushMode.FLUSH_BUSY)
    await wait_runner_amount(runner_manager_with_one_runner, 0)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_runner_normal_lifecycle(
    runner_manager_with_one_runner: RunnerManager,
    test_github_branch: Branch,
    github_repository: Repository,
    runner_label: str,
    log_dir_base_path: dict[str, Path],
):
    """
    Arrange: RunnerManager with one runner. Clean metric logs.
    Act:
        1. Start a test workflow for the runner.
        2. Run cleanup.
    Assert:
        1. The workflow complete successfully.
        2. The runner should be deleted. The metrics should be recorded.
    """
    metric_log_path = log_dir_base_path["metric_log"]
    metric_log_existing_content = metric_log_path.read_text(encoding="utf-8")

    workflow = await dispatch_workflow(
        app=None,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": runner_label, "minutes": "0"},
        wait=False,
    )
    await wait_for(lambda: workflow_is_status(workflow, "completed"))

    issue_metrics_events = runner_manager_with_one_runner.cleanup()
    assert issue_metrics_events[events.RunnerStart] == 1
    assert issue_metrics_events[events.RunnerStop] == 1

    metric_log_full_content = metric_log_path.read_text(encoding="utf-8")
    assert metric_log_full_content.startswith(
        metric_log_existing_content
    ), "The metric log was modified in ways other than appending"
    metric_log_new_content = metric_log_full_content[len(metric_log_existing_content) :]
    metric_logs = [json.loads(metric) for metric in metric_log_new_content.splitlines()]
    assert (
        len(metric_logs) == 2
    ), "Assuming two events should be runner_start and runner_stop, modify this if new events are added"
    assert metric_logs[0]["event"] == "runner_start"
    assert metric_logs[0]["workflow"] == "Workflow Dispatch Wait Tests"
    assert metric_logs[1]["event"] == "runner_stop"
    assert metric_logs[1]["workflow"] == "Workflow Dispatch Wait Tests"

    await wait_runner_amount(runner_manager_with_one_runner, 0)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_runner_spawn_two(
    runner_manager: RunnerManager, openstack_runner_manager: OpenStackRunnerManager
) -> None:
    """
    Arrange: RunnerManager instance with no runners.
    Act:
        1. Create two runner.
        2. Delete all idle runner.
    Assert:
        1. Two active idle runner.
        2. No runners.
    """
    # 1.
    runner_id_list = runner_manager.create_runners(2)
    assert isinstance(runner_id_list, tuple)
    assert len(runner_id_list) == 2

    try:
        await wait_runner_amount(runner_manager, 2)
    except TimeoutError as err:
        raise AssertionError("Test arrange failed: Expect two runner") from err

    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert len(runner_list) == 2

    # 3.
    runner_manager.flush_runners(flush_mode=FlushMode.FLUSH_IDLE)
    await wait_runner_amount(runner_manager, 0)
