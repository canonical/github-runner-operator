# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Iterable
import pytest

from charm_state import GitHubRepo
from manager.cloud_runner_manager import InstanceId
from manager.runner_manager import FlushMode, RunnerManager, RunnerManagerConfig
from manager.runner_scaler import RunnerScaler
from tests.unit.mock_runner_managers import (
    MockCloudRunnerManager,
    MockGitHubRunnerManager,
    SharedMockRunnerManagerState,
)


def mock_runner_manager_spawn_runners(create_runner_args: Iterable[RunnerManager._CreateRunnerArgs]) -> tuple[InstanceId, ...]: 
    """Mock _spawn_runners method of RunnerManager.
    
    The _spawn_runners method uses multi-process, which copies the object, e.g., the mocks.
    There is easy way to sync the state of the mocks object across processes. Replacing the 
    _spawn_runner to remove the multi-process.pool is an easier approach.
    """
    return tuple(RunnerManager._create_runner(arg) for arg in create_runner_args)


@pytest.fixture(scope="function", name="runner_manager")
def runner_manager_fixture(monkeypatch) -> RunnerManager:
    state = SharedMockRunnerManagerState()
    mock_cloud = MockCloudRunnerManager(state)
    mock_path = GitHubRepo("mock_owner", "mock_repo")
    mock_github = MockGitHubRunnerManager(mock_cloud.name_prefix, mock_path, state)

    monkeypatch.setattr("manager.runner_manager.RunnerManager._spawn_runners", mock_runner_manager_spawn_runners)
    config = RunnerManagerConfig("mock_token", mock_path)
    runner_manager = RunnerManager(mock_cloud, config)
    runner_manager._github = mock_github
    return runner_manager


@pytest.fixture(scope="function", name="runner_scaler")
def runner_scaler_fixture(runner_manager: RunnerManager) -> RunnerScaler:
    return RunnerScaler(runner_manager)


def assert_runner_info(
    runner_scaler: RunnerScaler, online: int = 0, offline: int = 0, unknown: int = 0
) -> None:
    """Assert runner info contains a certain amount of runners.

    Args:
        runner_scaler: The RunnerScaler to get information from.
        online: The number of online runners to assert for.
        offline: The number of offline runners to assert for.
        unknown: The number of unknown runners to assert for.
    """
    info = runner_scaler.get_runner_info()
    assert info["offline"] == offline
    assert info["online"] == online
    assert info["unknown"] == unknown
    assert isinstance(info["runners"], tuple)
    assert len(info["runners"]) == online


def test_get_no_runner(runner_scaler: RunnerScaler):
    """
    Arrange: A RunnerScaler with no runners.
    Act: Get runner information.
    Assert: Information should contain no runners.
    """
    assert_runner_info(runner_scaler, online=0)


def test_flush_no_runner(runner_scaler: RunnerScaler):
    """
    Arrange: A RunnerScaler with no runners.
    Act:
        1. Flush idle runners.
        2. Flush busy runners.
    Assert:
        1. No change in number of runners. Runner info should contain no runners.
        2. No change in number of runners.
    """
    # 1.
    diff = runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)

    # 2.
    diff = runner_scaler.flush(flush_mode=FlushMode.FLUSH_BUSY)
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)


def test_reconcile_runner_create_one(runner_scaler: RunnerScaler):
    """
    Arrange: A RunnerScaler with no runners.
    Act: Reconcile to no runners.
    Assert: No changes. Runner info should contain no runners.
    """
    diff = runner_scaler.reconcile(num_of_runner=0)
    assert diff == 0
    assert_runner_info(runner_scaler, online=0)


def test_one_runner(runner_scaler: RunnerScaler):
    """
    Arrange: A RunnerScaler with no runners.
    Act:
        1. Reconcile to one runner.
        2. Reconcile to one runner.
        3. Flush idle runners.
        4. Reconcile to one runner.
    Assert:
        1. Runner info has one runner.
        2. No changes to number of runner.
        3. Runner info has one runner.
    """
    # 1.
    diff = runner_scaler.reconcile(1)
    assert diff == 1
    assert_runner_info(runner_scaler, online=1)

    # 2.
    diff = runner_scaler.reconcile(1)
    assert diff == 0
    assert_runner_info(runner_scaler, online=1)

    # 3.
    runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
    assert_runner_info(runner_scaler, online=0)

    # 3.
    diff = runner_scaler.reconcile(1)
    assert diff == 1
    assert_runner_info(runner_scaler, online=1)
