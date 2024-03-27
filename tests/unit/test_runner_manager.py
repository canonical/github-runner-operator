# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of RunnerManager class."""
import random
import secrets
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from _pytest.monkeypatch import MonkeyPatch

import shared_fs
from charm_state import (
    Arch,
    CharmConfig,
    CharmState,
    GithubOrg,
    GithubRepo,
    ProxyConfig,
    VirtualMachineResources,
)
from errors import IssueMetricEventError, RunnerBinaryError
from github_type import RunnerApplication
from metrics import Reconciliation, RunnerInstalled, RunnerStart, RunnerStop
from runner import Runner, RunnerStatus
from runner_manager import BUILD_IMAGE_SCRIPT_FILENAME, RunnerManager, RunnerManagerConfig
from runner_metrics import RUNNER_INSTALLED_TS_FILE_NAME
from runner_type import RunnerByHealth
from shared_fs import SharedFilesystem
from tests.unit.mock import TEST_BINARY

RUNNER_MANAGER_TIME_MODULE = "runner_manager.time.time"
TEST_PROXY_SERVER_URL = "http://proxy.server:1234"


@pytest.fixture(scope="function", name="token")
def token_fixture():
    return secrets.token_hex()


@pytest.fixture(scope="function", name="charm_config")
def charm_config_fixture():
    """Mock charm config instance."""
    mock_charm_config = MagicMock(spec=CharmConfig)
    mock_charm_config.labels = ("test",)
    return mock_charm_config


@pytest.fixture(scope="function", name="charm_state")
def charm_state_fixture(charm_config: MagicMock):
    mock = MagicMock(spec=CharmState)
    mock.is_metrics_logging_available = False
    mock.arch = Arch.X64
    mock.ssh_debug_connections = None
    mock.charm_config = charm_config
    return mock


@pytest.fixture(
    scope="function",
    name="runner_manager",
    params=[
        (GithubOrg("test_org", "test_group"), ProxyConfig()),
        (
            GithubRepo("test_owner", "test_repo"),
            ProxyConfig(
                no_proxy="test_no_proxy",
                http=TEST_PROXY_SERVER_URL,
                https=TEST_PROXY_SERVER_URL,
                use_aproxy=False,
            ),
        ),
    ],
)
def runner_manager_fixture(request, tmp_path, monkeypatch, token, charm_state):
    charm_state.proxy_config = request.param[1]
    monkeypatch.setattr(
        "runner_manager.RunnerManager.runner_bin_path", tmp_path / "mock_runner_binary"
    )
    pool_path = tmp_path / "test_storage"
    pool_path.mkdir(exist_ok=True)

    runner_manager = RunnerManager(
        "test app",
        "0",
        RunnerManagerConfig(
            path=request.param[0],
            token=token,
            image="jammy",
            service_token=secrets.token_hex(16),
            lxd_storage_path=pool_path,
            charm_state=charm_state,
        ),
    )
    runner_manager.runner_bin_path.write_bytes(TEST_BINARY)
    return runner_manager


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("metrics.issue_event", issue_event_mock)
    return issue_event_mock


@pytest.fixture(autouse=True, name="shared_fs")
def shared_fs_fixture(tmp_path: Path, monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the shared filesystem module."""
    shared_fs_mock = MagicMock(spec=shared_fs)
    monkeypatch.setattr("runner_manager.shared_fs", shared_fs_mock)
    monkeypatch.setattr("runner.shared_fs", shared_fs_mock)
    return shared_fs_mock


@pytest.fixture(autouse=True, name="runner_metrics")
def runner_metrics_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the runner metrics module."""
    runner_metrics_mock = MagicMock()
    monkeypatch.setattr("runner_manager.runner_metrics", runner_metrics_mock)
    return runner_metrics_mock


@pytest.mark.parametrize(
    "arch",
    [
        pytest.param(Arch.ARM64),
        pytest.param(Arch.X64),
    ],
)
def test_get_latest_runner_bin_url(runner_manager: RunnerManager, arch: Arch, charm_state):
    """
    arrange: Nothing.
    act: Get runner bin url of existing binary.
    assert: Correct mock data returned.
    """
    charm_state.arch = arch
    mock_gh_client = MagicMock()
    app = RunnerApplication(
        os="linux",
        architecture=arch.value,
        download_url=(download_url := "https://www.example.com"),
        filename=(filename := "test_runner_binary"),
    )
    mock_gh_client.get_runner_application.return_value = app
    runner_manager._clients.github = mock_gh_client

    runner_bin = runner_manager.get_latest_runner_bin_url(os_name="linux")
    assert runner_bin["os"] == "linux"
    assert runner_bin["architecture"] == arch.value
    assert runner_bin["download_url"] == download_url
    assert runner_bin["filename"] == filename


def test_get_latest_runner_bin_url_missing_binary(runner_manager: RunnerManager):
    """
    arrange: Given a mocked GH API client that does not return any runner binaries.
    act: Get runner bin url of non-existing binary.
    assert: Error related to runner bin raised.
    """
    runner_manager._clients.github = MagicMock()
    runner_manager._clients.github.get_runner_application.side_effect = RunnerBinaryError

    with pytest.raises(RunnerBinaryError):
        runner_manager.get_latest_runner_bin_url(os_name="not_exist")


def test_update_runner_bin(runner_manager: RunnerManager):
    """
    arrange: Remove the existing runner binary.
    act: Update runner binary.
    assert: Runner binary in runner manager is set.
    """

    class MockRequestLibResponse:
        """A mock requests library response."""

        def __init__(self, *args, **kwargs):
            """Initialize successful requests library response.

            Args:
                args: Placeholder for positional arguments.
                kwargs: Placeholder for keyword arguments.
            """
            self.status_code = 200

        def iter_content(self, *args, **kwargs):
            """Mock content iterator returning an iterator over a single test runner binary.

            Args:
                args: Placeholder positional arguments.
                kwargs: Placeholder keyword arguments.

            Returns:
                An iterator over a single test runner binary.
            """
            return iter([TEST_BINARY])

    runner_manager.runner_bin_path.unlink(missing_ok=True)

    runner_manager.session.get = MockRequestLibResponse
    runner_bin = runner_manager.get_latest_runner_bin_url(os_name="linux")

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
        """Create three mock runners.

        Returns:
            Three mock runners.
        """
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
    runner_manager: RunnerManager,
    monkeypatch: MonkeyPatch,
    issue_event_mock: MagicMock,
    charm_state: MagicMock,
):
    """
    arrange: Enable issuing of metrics and mock timestamps.
    act: Reconcile to create a runner.
    assert: The expected event is issued.
    """
    charm_state.is_metrics_logging_available = True
    t_mock = MagicMock(return_value=12345)
    monkeypatch.setattr(RUNNER_MANAGER_TIME_MODULE, t_mock)

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    issue_event_mock.assert_has_calls(
        [call(event=RunnerInstalled(timestamp=12345, flavor=runner_manager.app_name, duration=0))]
    )


def test_reconcile_issues_no_runner_installed_event_if_metrics_disabled(
    runner_manager: RunnerManager, issue_event_mock: MagicMock, charm_state: MagicMock
):
    """
    arrange: Disable issuing of metrics.
    act: Reconcile to create a runner.
    assert: The expected event is not issued.
    """
    charm_state.is_metrics_logging_available = False

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    issue_event_mock.assert_not_called()


def test_reconcile_error_on_issue_event_is_ignored(
    runner_manager: RunnerManager,
    issue_event_mock: MagicMock,
    charm_state: MagicMock,
):
    """
    arrange: Enable issuing of metrics and mock the metric issuing to raise an expected error.
    act: Reconcile.
    assert: No error is raised.
    """
    charm_state.is_metrics_logging_available = True

    issue_event_mock.side_effect = IssueMetricEventError("test error")

    delta = runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert delta == 1


def test_reconcile_issues_reconciliation_metric_event(
    runner_manager: RunnerManager,
    monkeypatch: MonkeyPatch,
    issue_event_mock: MagicMock,
    runner_metrics: MagicMock,
    charm_state: MagicMock,
):
    """
    arrange: \
        - Enable issuing of metrics \
        - Mock timestamps \
        - Mock the result of runner_metrics.issue_event to contain 2 RunnerStart and 1 RunnerStop \
            events, meaning one runner was active and one crashed. \
        - Create two online runners , one active and one idle.
    act: Reconcile.
    assert: The expected event is issued. We expect two idle runners and one crashed runner
     to be reported.
    """
    charm_state.is_metrics_logging_available = True
    t_mock = MagicMock(return_value=12345)
    monkeypatch.setattr(RUNNER_MANAGER_TIME_MODULE, t_mock)
    runner_metrics.extract.return_value = (MagicMock() for _ in range(2))
    runner_metrics.issue_events.side_effect = [{RunnerStart, RunnerStop}, {RunnerStart}]

    online_idle_runner_name = f"{runner_manager.instance_name}-0"
    offline_idle_runner_name = f"{runner_manager.instance_name}-1"
    active_runner_name = f"{runner_manager.instance_name}-2"

    def mock_get_runners():
        """Create three mock runners where one is busy.

        Returns:
            Mock runners with one busy runner.
        """
        runners = []

        online_idle_runner = RunnerStatus(runner_id=0, exist=True, online=True, busy=False)
        offline_idle_runner = RunnerStatus(runner_id=1, exist=True, online=False, busy=False)
        active_runner = RunnerStatus(runner_id=2, exist=True, online=True, busy=True)

        for runner_status, runner_config in zip(
            (online_idle_runner, offline_idle_runner, active_runner),
            (online_idle_runner_name, offline_idle_runner_name, active_runner_name),
        ):
            config = MagicMock()
            config.name = runner_config
            runners.append(
                Runner(
                    clients=MagicMock(),
                    runner_config=config,
                    runner_status=runner_status,
                    instance=None,
                )
            )

        return runners

    # Create online runners.
    runner_manager._get_runners = mock_get_runners
    runner_manager._get_runner_health_states = lambda: RunnerByHealth(
        healthy=(
            online_idle_runner_name,
            offline_idle_runner_name,
            active_runner_name,
        ),
        unhealthy=(),
    )

    runner_manager.reconcile(
        quantity=random.randint(0, 5), resources=VirtualMachineResources(2, "7GiB", "10Gib")
    )

    issue_event_mock.assert_any_call(
        event=Reconciliation(
            timestamp=12345,
            flavor=runner_manager.app_name,
            crashed_runners=1,
            idle_runners=2,
            duration=0,
        )
    )


def test_reconcile_places_timestamp_in_newly_created_runner(
    runner_manager: RunnerManager,
    monkeypatch: MonkeyPatch,
    shared_fs: MagicMock,
    tmp_path: Path,
    charm_state: MagicMock,
):
    """
    arrange: Enable issuing of metrics, mock timestamps and create the directory for the shared\
        filesystem.
    act: Reconcile to create a runner.
    assert: The expected timestamp is placed in the shared filesystem.
    """
    charm_state.is_metrics_logging_available = True
    t_mock = MagicMock(return_value=12345)
    monkeypatch.setattr(RUNNER_MANAGER_TIME_MODULE, t_mock)
    runner_shared_fs = tmp_path / "runner_fs"
    runner_shared_fs.mkdir()
    fs = SharedFilesystem(path=runner_shared_fs, runner_name="test_runner")
    shared_fs.get.return_value = fs

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert (fs.path / RUNNER_INSTALLED_TS_FILE_NAME).exists()
    assert (fs.path / RUNNER_INSTALLED_TS_FILE_NAME).read_text() == "12345"


def test_reconcile_error_on_placing_timestamp_is_ignored(
    runner_manager: RunnerManager, shared_fs: MagicMock, tmp_path: Path, charm_state: MagicMock
):
    """
    arrange: Enable issuing of metrics and do not create the directory for the shared filesystem\
        in order to let a FileNotFoundError to be raised inside the RunnerManager.
    act: Reconcile to create a runner.
    assert: No exception is raised.
    """
    charm_state.is_metrics_logging_available = True
    runner_shared_fs = tmp_path / "runner_fs"
    fs = SharedFilesystem(path=runner_shared_fs, runner_name="test_runner")
    shared_fs.get.return_value = fs

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert not (fs.path / RUNNER_INSTALLED_TS_FILE_NAME).exists()


def test_reconcile_places_no_timestamp_in_newly_created_runner_if_metrics_disabled(
    runner_manager: RunnerManager, shared_fs: MagicMock, tmp_path: Path, charm_state: MagicMock
):
    """
    arrange: Disable issuing of metrics, mock timestamps and the shared filesystem module.
    act: Reconcile to create a runner.
    assert: No timestamp is placed in the shared filesystem.
    """
    charm_state.is_metrics_logging_available = False

    fs = SharedFilesystem(path=tmp_path, runner_name="test_runner")
    shared_fs.get.return_value = fs

    runner_manager.reconcile(1, VirtualMachineResources(2, "7GiB", "10Gib"))

    assert not (fs.path / RUNNER_INSTALLED_TS_FILE_NAME).exists()


def test_schedule_build_runner_image(
    runner_manager: RunnerManager,
    tmp_path: Path,
    charm_state: CharmState,
    monkeypatch: MonkeyPatch,
):
    """
    arrange: Mock the cron path and the randint function.
    act: Schedule the build runner image.
    assert: The cron file is created with the expected content.
    """
    runner_manager.cron_path = tmp_path / "cron"
    runner_manager.cron_path.mkdir()
    monkeypatch.setattr(random, "randint", MagicMock(spec=random.randint, return_value=4))

    runner_manager.schedule_build_runner_image()

    cronfile = runner_manager.cron_path / "build-runner-image"
    http = charm_state.proxy_config.http or "''"
    https = charm_state.proxy_config.https or "''"
    no_proxy = charm_state.proxy_config.no_proxy or "''"

    cmd = f"/usr/bin/bash {BUILD_IMAGE_SCRIPT_FILENAME.absolute()} {http} {https} {no_proxy}"

    assert cronfile.exists()
    assert cronfile.read_text() == f"4 4,10,16,22 * * * ubuntu {cmd}\n"
