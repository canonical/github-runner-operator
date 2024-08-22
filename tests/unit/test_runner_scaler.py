# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import pytest

from charm_state import GitHubRepo
from manager.runner_manager import RunnerManager, RunnerManagerConfig
from manager.runner_scaler import RunnerScaler
from tests.unit.mock_runner_managers import (
    MockCloudRunnerManager,
    MockGitHubRunnerManager,
    SharedMockRunnerManagerState,
)


@pytest.fixture(name="runner_manager")
def runner_manager_fixture() -> RunnerManager:
    state = SharedMockRunnerManagerState()
    mock_cloud = MockCloudRunnerManager(state)
    mock_path = GitHubRepo("mock_owner", "mock_repo")
    mock_github = MockGitHubRunnerManager(mock_cloud.name_prefix, mock_path, state)

    config = RunnerManagerConfig("mock_token", mock_path)
    runner_manager = RunnerManager(mock_cloud, config)
    runner_manager._github = mock_github
    return runner_manager


@pytest.fixture(name="runner_scaler")
def runner_scaler_fixture(runner_manager: RunnerManager) -> RunnerScaler:
    return RunnerScaler(runner_manager)


def test_get_no_runner(runner_scaler: RunnerScaler):
    info = runner_scaler.get_runner_info()
    assert info["offline"] == 0
    assert info["online"] == 0
    assert info["unknown"] == 0
    assert info["runners"] == tuple()
