# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of RunnerManager class."""

import secrets
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from requests import HTTPError

from errors import RunnerBinaryError
from metrics import RunnerInstalled
from runner import Runner, RunnerStatus
from runner_manager import RunnerManager, RunnerManagerConfig
from runner_type import GitHubOrg, GitHubRepo, RunnerByHealth, VirtualMachineResources
from tests.unit.mock import TEST_BINARY


@pytest.fixture(scope="function", name="token")
def token_fixture():
    return secrets.token_hex()


@pytest.fixture(
    scope="function",
    name="runner_manager",
    params=[
        (GitHubOrg("test_org", "test_group"), {}),
        (
            GitHubRepo("test_owner", "test_repo"),
            {"no_proxy": "test_no_proxy", "http": "test_http", "https": "test_https"},
        ),
    ],
)
def runner_manager_fixture(request, tmp_path, monkeypatch, token):
    monkeypatch.setattr(
        "runner_manager.RunnerManager.runner_bin_path", tmp_path / "mock_runner_binary"
    )
    pool_path = tmp_path / "test_storage"
    pool_path.mkdir(exist_ok=True)

    runner_manager = RunnerManager(
        "test app",
        "0",
        RunnerManagerConfig(
            request.param[0], token, "jammy", secrets.token_hex(16), pool_path, False
        ),
        proxies=request.param[1],
    )
    runner_manager.runner_bin_path.write_bytes(TEST_BINARY)
    return runner_manager


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("metrics.issue_event", issue_event_mock)
    return issue_event_mock


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
    arrange: Remove the existing runner binary.
    act: Update runner binary.
    assert: Runner binary in runner manager is set.
    """

    class MockRequestLibResponse:
        def __init__(self, *arg, **kargs):
            self.status_code = 200

        def iter_content(self, *arg, **kargs):
            return iter([TEST_BINARY])

    runner_manager.runner_bin_path.unlink(missing_ok=True)

    runner_manager.session.get = MockRequestLibResponse
    runner_bin = runner_manager.get_latest_runner_bin_url(os_name="linux", arch_name="x64")

    runner_manager.update_runner_bin(runner_bin)

    assert runner_manager.runner_bin_path.read_bytes() == TEST_BINARY


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
            # 0 is a mock runner id.
            status = RunnerStatus(0, True, True, False)
            runners.append(Runner(MagicMock(), MagicMock(), status, None))
        return runners

    # Create online runners.
    runner_manager._get_runners = mock_get_runners
    runner_manager._get_runner_health_states = lambda: RunnerByHealth(
        (
            f"{runner_manager.instance_name}-0",
            f"{runner_manager.instance_name}-1",
            f"{runner_manager.instance_name}-2",
        ),
        (),
    )

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


def test_reconcile_issues_runner_installed_event(
    runner_manager: RunnerManager, monkeypatch: MonkeyPatch, issue_event_mock: MagicMock
):
    """
    arrange: Enable issuing of metrics, mock the issuing and timestamps.
    act: Reconcile to create a runner.
    assert: The expected event is issued.
    """
    runner_manager.config.issue_metrics = True
    t_mock = MagicMock(return_value=12345)
    monkeypatch.setattr("metrics.time.time", t_mock)

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    issue_event_mock.assert_called_once_with(
        RunnerInstalled(timestamp=12345, flavor=runner_manager.app_name, duration=0)
    )


def test_reconcile_issues_no_runner_installed_event_if_metrics_disabled(
    runner_manager: RunnerManager, issue_event_mock: MagicMock
):
    """
    arrange: Disable issuing of metrics, mock the issuing and timestamps.
    act: Reconcile to create a runner.
    assert: The expected event is not issued.
    """
    runner_manager.config.issue_metrics = False

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    issue_event_mock.assert_not_called()


def test_reconcile_error_on_runner_installed_event_are_ignored(
    runner_manager: RunnerManager,
    issue_event_mock: MagicMock,
):
    """
    arrange: Enable issuing of metrics and mock the issuing to raise an expected error.
    act: Reconcile to create a runner.
    assert: No error is raised.
    """
    runner_manager.config.issue_metrics = True
    issue_event_mock.side_effect = HTTPError

    delta = runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert delta == 1
