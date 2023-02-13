# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of RunnerManager class."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errors import RunnerBinaryError
from runner import Runner, RunnerStatus
from runner_manager import RunnerManager, RunnerManagerConfig
from runner_type import GitHubOrg, GitHubRepo, VirtualMachineResources
from tests.unit.mock import TEST_BINARY


@pytest.fixture(
    scope="function",
    name="runner_manager",
    params=[
        (GitHubOrg("test_org"), {}),
        (
            GitHubRepo("test_owner", "test_repo"),
            {"no_proxy": "test_no_proxy", "http": "test_http", "https": "test_https"},
        ),
    ],
)
def runner_manager_fixture(request, tmp_path):
    runner_manager = RunnerManager(
        "test app", RunnerManagerConfig(request.param[0], "mock token"), proxies=request.param[1]
    )
    # Fake having a binary by setting to non-None value.
    runner_manager.runner_bin_path = tmp_path / "test_binary"
    return runner_manager


def test_get_latest_runner_bin_url(runner_manager: RunnerManager):
    """
    arrange: Nothing.
    act: Get runner bin url of existing binary.
    assert: Correct mock data returned.
    """
    runner_bin = runner_manager.get_latest_runner_bin_url(os_name="linux", arch_name="x64")
    assert runner_bin["os"] == "linux"
    assert runner_bin["architecture"] == "x64"
    assert runner_bin["download_url"] == "https://www.example.com"
    assert runner_bin["filename"] == "test_runner_binary"


def test_get_latest_runner_bin_url_missing_binary(runner_manager: RunnerManager):
    """
    arrange: Nothing.
    act: Get runner bin url of non-existing binary.
    assert: Error related to runner bin raised.
    """
    with pytest.raises(RunnerBinaryError):
        runner_manager.get_latest_runner_bin_url(os_name="not_exist", arch_name="not_exist")


def test_update_runner_bin(runner_manager: RunnerManager):
    """
    arrange: Nothing.
    act: Update runner binary.
    assert: Runner binary in runner manager is set.
    """

    class MockRequestLibResponse:
        def __init__(self, *arg, **kargs):
            self.status_code = 200

        def iter_content(self, *arg, **kargs):
            return iter([TEST_BINARY])

    runner_manager.session.get = MockRequestLibResponse
    # Remove the fake binary in fixture.
    runner_manager.runner_bin_path = None
    runner_bin = runner_manager.get_latest_runner_bin_url(os_name="linux", arch_name="x64")

    runner_manager.update_runner_bin(runner_bin)
    assert runner_manager.runner_bin_path is not None


def test_reconcile_zero_count(runner_manager: RunnerManager):
    """
    arrange: Nothing.
    act: Reconcile with the current amount of runner.
    assert: No error should be raised.
    """
    # Reconcile with no change to runner count.
    delta = runner_manager.reconcile(0, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert delta == 0


def test_reconcile_create_runner(runner_manager: RunnerManager):
    """
    arrange: Nothing.
    act: Reconcile to create a runner.
    assert: One runner should be created.
    """
    # Create a runner.
    delta = runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert delta == 1


def test_reconcile_remove_runner(runner_manager: RunnerManager):
    """
    arrange: Create online runners.
    act: Reconcile to remove a runner.
    assert: One runner should be removed.
    """

    def mock_get_runners():
        """Create three mock runners."""
        runners = []
        for _ in range(3):
            status = RunnerStatus(True, True, False)
            runners.append(Runner(MagicMock(), MagicMock(), status, None))
        return runners

    # Create online runners.
    runner_manager._get_runners = mock_get_runners

    delta = runner_manager.reconcile(2, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert delta == -1


def test_reconcile(runner_manager: RunnerManager, tmp_path: Path):
    """
    arrange: Setup one runner.
    act: Reconcile with the current amount of runner.
    assert: Still have one runner.
    """
    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))
    # Reconcile with no change to runner count.
    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert len(runner_manager._get_runners()) == 1


def test_empty_flush(runner_manager: RunnerManager):
    """
    arrange: No initial runners.
    act: Perform flushing with no runners.
    assert: No error thrown.
    """
    # Verifying the RunnerManager does not crash if flushing with no runners.
    runner_manager.flush()


def test_flush(runner_manager: RunnerManager, tmp_path: Path):
    """
    arrange: Create some runners.
    act: Perform flushing.
    assert: No runners.
    """
    # Create a runner.
    runner_manager.reconcile(2, VirtualMachineResources(2, "7GiB", "10Gib"))

    runner_manager.flush()
    assert len(runner_manager._get_runners()) == 0
