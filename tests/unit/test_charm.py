# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for GithubRunnerCharm."""
import os
import secrets
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml
from ops.model import BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.testing import Harness

from charm import GithubRunnerCharm
from charm_state import (
    GROUP_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    VM_CPU_CONFIG_NAME,
    VM_DISK_CONFIG_NAME,
    Arch,
    GithubOrg,
    GithubRepo,
    ProxyConfig,
    VirtualMachineResources,
)
from errors import LogrotateSetupError, MissingIntegrationDataError, RunnerError, SubprocessError
from event_timer import EventTimer, TimerEnableError
from firewall import FirewallEntry
from github_type import GitHubRunnerStatus
from metrics.events import METRICS_LOGROTATE_CONFIG
from metrics.runner_logs import RUNNER_LOGROTATE_CONFIG
from reactive.runner_manager import REACTIVE_ERROR_LOGROTATE_CONFIG, REACTIVE_LOGROTATE_CONFIG
from runner_manager import RunnerInfo, RunnerManagerConfig

TEST_PROXY_SERVER_URL = "http://proxy.server:1234"


def raise_runner_error(*args, **kwargs):
    """Stub function to raise RunnerError.

    Args:
        args: Positional argument placeholder.
        kwargs: Keyword argument placeholder.

    Raises:
        RunnerError: Always.
    """
    raise RunnerError("mock error")


def raise_subprocess_error(*args, **kwargs):
    """Stub function to raise SubprocessError.

    Args:
        args: Positional argument placeholder.
        kwargs: Keyword argument placeholder.

    Raises:
        SubprocessError: Always.
    """
    raise SubprocessError(cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr")


def raise_url_error(*args, **kwargs):
    """Stub function to raise URLError.

    Args:
        args: Positional argument placeholder.
        kwargs: Keyword argument placeholder.

    Raises:
        URLError: Always.
    """
    raise urllib.error.URLError("mock error")


def mock_get_latest_runner_bin_url(os_name: str = "linux", arch: Arch = Arch.X64):
    """Stub function to return test runner_bin_url data.

    Args:
        os_name: OS name placeholder argument.
        arch: Architecture placeholder argument.

    Returns:
        MagicMock runner application.
    """
    mock = MagicMock()
    mock.download_url = "www.example.com"
    return mock


def mock_download_latest_runner_image(*args):
    """A stub function to download runner latest image.

    Args:
        args: Placeholder for positional arguments.

    Returns:
        Latest runner image test URL.
    """
    return "www.example.com"


def mock_get_github_info():
    """A stub function that returns mock Github runner information.

    Returns:
        RunnerInfo with different name, statuses, busy values.
    """
    return [
        RunnerInfo("test runner 0", GitHubRunnerStatus.ONLINE.value, True),
        RunnerInfo("test runner 1", GitHubRunnerStatus.ONLINE.value, False),
        RunnerInfo("test runner 2", GitHubRunnerStatus.OFFLINE.value, False),
        RunnerInfo("test runner 3", GitHubRunnerStatus.OFFLINE.value, False),
        RunnerInfo("test runner 4", "unknown", False),
    ]


def setup_charm_harness(monkeypatch: pytest.MonkeyPatch, runner_bin_path: Path) -> Harness:
    """Setup harness with patched runner manager methods.

    Args:
        monkeypatch: Instance of pytest monkeypatch for patching RunnerManager methods.
        runner_bin_path: Runner binary temporary path fixture.

    Returns:
        Harness with patched RunnerManager instance.
    """

    def stub_update_runner_bin(*args, **kwargs) -> None:
        """Update runner bin stub function.

        Args:
            args: Placeholder for positional argument values.
            kwargs: Placeholder for keyword argument values.
        """
        runner_bin_path.touch()

    harness = Harness(GithubRunnerCharm)
    harness.update_config({PATH_CONFIG_NAME: "mock/repo", TOKEN_CONFIG_NAME: "mocktoken"})
    harness.begin()
    monkeypatch.setattr("runner_manager.RunnerManager.update_runner_bin", stub_update_runner_bin)
    monkeypatch.setattr("runner_manager.RunnerManager._runners_in_pre_job", lambda self: False)
    monkeypatch.setattr("charm.EventTimer.ensure_event_timer", MagicMock())
    monkeypatch.setattr("charm.logrotate.setup", MagicMock())
    monkeypatch.setattr("charm.logrotate.configure", MagicMock())
    return harness


@pytest.fixture(name="harness")
def harness_fixture(monkeypatch, runner_binary_path: Path) -> Harness:
    return setup_charm_harness(monkeypatch, runner_binary_path)


@patch.dict(
    os.environ,
    {
        "JUJU_CHARM_HTTPS_PROXY": TEST_PROXY_SERVER_URL,
        "JUJU_CHARM_HTTP_PROXY": TEST_PROXY_SERVER_URL,
        "JUJU_CHARM_NO_PROXY": "127.0.0.1,localhost",
    },
)
def test_proxy_setting(harness: Harness):
    """
    arrange: Set up charm under proxied environment.
    act: Nothing.
    assert: The proxy configuration are set.
    """
    state = harness.charm._setup_state()
    assert state.proxy_config.https == TEST_PROXY_SERVER_URL
    assert state.proxy_config.http == TEST_PROXY_SERVER_URL
    assert state.proxy_config.no_proxy == "127.0.0.1,localhost"


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("install", id="Install"),
        pytest.param("upgrade_charm", id="Upgrade"),
    ],
)
def test_common_install_code(
    hook: str, harness: Harness, exec_command: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up charm.
    act: Fire install/upgrade event.
    assert: Common install commands are run on the mock.
    """
    monkeypatch.setattr("charm.logrotate.setup", setup_logrotate := MagicMock())
    monkeypatch.setattr("charm.logrotate.configure", config_logrotate := MagicMock())

    monkeypatch.setattr(
        "runner_manager.RunnerManager.schedule_build_runner_image",
        schedule_build_runner_image := MagicMock(),
    )
    event_timer_mock = MagicMock(spec=EventTimer)
    harness.charm._event_timer = event_timer_mock

    getattr(harness.charm.on, hook).emit()
    calls = [
        call(["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"]),
        call(["/snap/bin/lxd", "init", "--auto"]),
        call(["/usr/bin/systemctl", "enable", "repo-policy-compliance"]),
    ]

    exec_command.assert_has_calls(calls, any_order=True)
    setup_logrotate.assert_called_once()
    config_logrotate.assert_has_calls(
        [
            call(REACTIVE_LOGROTATE_CONFIG),
            call(REACTIVE_ERROR_LOGROTATE_CONFIG),
            call(METRICS_LOGROTATE_CONFIG),
            call(RUNNER_LOGROTATE_CONFIG),
        ]
    )
    schedule_build_runner_image.assert_called_once()
    event_timer_mock.ensure_event_timer.assert_called_once()


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("install", id="Install"),
        pytest.param("upgrade_charm", id="Upgrade"),
    ],
)
def test_common_install_code_does_not_rebuild_image(
    hook: str, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up charm and runner manager to not have runner image.
    act: Fire upgrade event.
    assert: Image is not rebuilt.
    """
    monkeypatch.setattr(
        "runner_manager.RunnerManager.build_runner_image",
        build_runner_image := MagicMock(),
    )
    monkeypatch.setattr(
        "runner_manager.RunnerManager.has_runner_image",
        MagicMock(return_value=True),
    )
    getattr(harness.charm.on, hook).emit()

    assert not build_runner_image.called


def test_on_config_changed_failure(harness: Harness):
    """
    arrange: Set up charm.
    act: Fire config changed event to use aproxy without configured http proxy.
    assert: Charm is in blocked state.
    """
    harness.update_config({USE_APROXY_CONFIG_NAME: True})

    assert isinstance(harness.charm.unit.status, BlockedStatus)
    assert "Invalid proxy configuration" in harness.charm.unit.status.message


def test_get_runner_manager(harness: Harness):
    """
    arrange: Set up charm.
    act: Get runner manager.
    assert: Runner manager is returned with the correct config.
    """
    state = harness.charm._setup_state()
    runner_manager = harness.charm._get_runner_manager(state)
    assert runner_manager is not None
    assert runner_manager.config.token == "mocktoken"
    assert runner_manager.proxies == ProxyConfig(
        http=None, https=None, no_proxy=None, use_aproxy=False
    )


def test_on_flush_runners_action_fail(harness: Harness, runner_binary_path: Path):
    """
    arrange: Set up charm without runner binary downloaded.
    act: Run flush runner action.
    assert: Action fail with missing runner binary.
    """
    runner_binary_path.unlink(missing_ok=True)
    mock_event = MagicMock()
    harness.charm._on_flush_runners_action(mock_event)
    mock_event.fail.assert_called_with(
        "GitHub runner application not downloaded; the charm will retry download on reconcile "
        "interval"
    )


def test_on_flush_runners_action_success(harness: Harness, runner_binary_path: Path):
    """
    arrange: Set up charm without runner binary downloaded.
    act: Run flush runner action.
    assert: Action fail with missing runner binary.
    """
    mock_event = MagicMock()
    runner_binary_path.touch()
    harness.charm._on_flush_runners_action(mock_event)
    mock_event.set_results.assert_called()


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("install", id="Install"),
        pytest.param("upgrade_charm", id="Upgrade"),
    ],
)
def test_on_install_failure(hook: str, harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Charm with mock setup_logrotate.
    act:
        1. Mock setup_logrotate fails.
        2. Mock _install_deps raises error.
    assert: Charm goes into error state in both cases.
    """
    monkeypatch.setattr("charm.logrotate.setup", setup_logrotate := unittest.mock.MagicMock())

    setup_logrotate.side_effect = LogrotateSetupError("Failed to setup logrotate")
    with pytest.raises(LogrotateSetupError) as exc:
        getattr(harness.charm.on, hook).emit()
    assert str(exc.value) == "Failed to setup logrotate"

    setup_logrotate.side_effect = None
    monkeypatch.setattr(GithubRunnerCharm, "_install_deps", raise_subprocess_error)
    with pytest.raises(SubprocessError) as exc:
        getattr(harness.charm.on, hook).emit()
    assert "mock stderr" in str(exc.value)


def test__refresh_firewall(monkeypatch, harness: Harness, runner_binary_path: Path):
    """
    arrange: given multiple tmate-ssh-server units in relation.
    act: when refresh_firewall is called.
    assert: the unit ip addresses are included in allowlist.
    """
    runner_binary_path.touch()

    relation_id = harness.add_relation("debug-ssh", "tmate-ssh-server")
    harness.add_relation_unit(relation_id, "tmate-ssh-server/0")
    harness.add_relation_unit(relation_id, "tmate-ssh-server/1")
    harness.add_relation_unit(relation_id, "tmate-ssh-server/2")
    test_unit_ip_addresses = ["127.0.0.1", "127.0.0.2", "127.0.0.3"]

    harness.update_relation_data(
        relation_id,
        "tmate-ssh-server/0",
        {
            "host": test_unit_ip_addresses[0],
            "port": "10022",
            "rsa_fingerprint": "SHA256:abcd",
            "ed25519_fingerprint": "abcd",
        },
    )
    harness.update_relation_data(
        relation_id,
        "tmate-ssh-server/1",
        {
            "host": test_unit_ip_addresses[1],
            "port": "10022",
            "rsa_fingerprint": "SHA256:abcd",
            "ed25519_fingerprint": "abcd",
        },
    )
    harness.update_relation_data(
        relation_id,
        "tmate-ssh-server/2",
        {
            "host": test_unit_ip_addresses[2],
            "port": "10022",
            "rsa_fingerprint": "SHA256:abcd",
            "ed25519_fingerprint": "abcd",
        },
    )

    monkeypatch.setattr("charm.Firewall", mock_firewall := unittest.mock.MagicMock())
    state = harness.charm._setup_state()
    harness.charm._refresh_firewall(state)
    mocked_firewall_instance = mock_firewall.return_value
    allowlist = mocked_firewall_instance.refresh_firewall.call_args_list[0][1]["allowlist"]
    assert all(
        FirewallEntry(ip) in allowlist for ip in test_unit_ip_addresses
    ), "Expected IP firewall entry not found in allowlist arg."


def test_charm_goes_into_waiting_state_on_missing_integration_data(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
):
    """
    arrange: Mock charm._setup_state to raise an MissingIntegrationDataError.
    act: Fire config changed event.
    assert: Charm is in blocked state.
    """
    setup_state_mock = MagicMock(side_effect=MissingIntegrationDataError("mock error"))
    monkeypatch.setattr(GithubRunnerCharm, "_setup_state", setup_state_mock)
    harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
    harness.charm.on.config_changed.emit()
    assert isinstance(harness.charm.unit.status, WaitingStatus)
    assert "mock error" in harness.charm.unit.status.message


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("database_created", id="Database Created"),
        pytest.param("endpoints_changed", id="Endpoints Changed"),
    ],
)
def test_database_integration_events_trigger_reconciliation(
    hook: str, monkeypatch: pytest.MonkeyPatch, harness: Harness
):
    """
    arrange: Mock charm._trigger_reconciliation.
    act: Fire mongodb relation events.
    assert: _trigger_reconciliation has been called.
    """
    reconcliation_mock = MagicMock()
    relation_mock = MagicMock()
    relation_mock.name = "mongodb"
    relation_mock.id = 0
    monkeypatch.setattr("charm.GithubRunnerCharm._trigger_reconciliation", reconcliation_mock)
    getattr(harness.charm.database.on, hook).emit(relation=relation_mock)
    reconcliation_mock.assert_called_once()


# New tests should not be added here. This should be refactored to pytest over time.
# New test should be written with pytest, similar to the above tests.
# Consider to rewrite test with pytest if the tests below needs to be changed.
class TestCharm(unittest.TestCase):
    """Test the GithubRunner charm."""

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_org_register(self, run, wt, mkdir, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config(
            {
                PATH_CONFIG_NAME: "mockorg",
                TOKEN_CONFIG_NAME: "mocktoken",
                GROUP_CONFIG_NAME: "mockgroup",
                RECONCILE_INTERVAL_CONFIG_NAME: 5,
            }
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        token = harness.charm.service_token
        state = harness.charm._setup_state()
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GithubOrg(org="mockorg", group="mockgroup"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.juju_storage_path,
                charm_state=state,
            ),
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_repo_register(self, run, wt, mkdir, rm):
        harness = Harness(GithubRunnerCharm)
        harness.update_config(
            {
                PATH_CONFIG_NAME: "mockorg/repo",
                TOKEN_CONFIG_NAME: "mocktoken",
                RECONCILE_INTERVAL_CONFIG_NAME: 5,
            }
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        token = harness.charm.service_token
        state = harness.charm._setup_state()
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GithubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.juju_storage_path,
                charm_state=state,
            ),
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_exceed_free_disk_size(self, run, wt, mkdir, rm):
        """
        arrange: Charm with 30GiB of storage for runner.
        act: Configuration that uses 100GiB of disk.
        assert: Charm enters block state.
        """
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url
        mock_rm.download_latest_runner_image = mock_download_latest_runner_image

        harness = Harness(GithubRunnerCharm)
        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()

        harness.update_config({VIRTUAL_MACHINES_CONFIG_NAME: 10})
        harness.charm.on.reconcile_runners.emit()
        assert harness.charm.unit.status == BlockedStatus(
            (
                "Required disk space for runners 102400.0MiB is greater than storage total size "
                "30720.0MiB"
            )
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_update_config(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url
        mock_rm.download_latest_runner_image = mock_download_latest_runner_image

        harness = Harness(GithubRunnerCharm)
        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()

        # update to 0 virtual machines
        harness.update_config({VIRTUAL_MACHINES_CONFIG_NAME: 0})
        harness.charm.on.reconcile_runners.emit()
        token = harness.charm.service_token
        state = harness.charm._setup_state()
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GithubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.juju_storage_path,
                charm_state=state,
            ),
        )
        mock_rm.reconcile.assert_called_with(0, VirtualMachineResources(2, "7GiB", "10GiB")),
        mock_rm.reset_mock()

        # update to 10 VMs with 4 cpu and 7GiB memory
        harness.update_config(
            {VIRTUAL_MACHINES_CONFIG_NAME: 5, VM_CPU_CONFIG_NAME: 4, VM_DISK_CONFIG_NAME: "6GiB"}
        )
        harness.charm.on.reconcile_runners.emit()
        token = harness.charm.service_token
        state = harness.charm._setup_state()
        rm.assert_called_with(
            "github-runner",
            "0",
            RunnerManagerConfig(
                path=GithubRepo(owner="mockorg", repo="repo"),
                token="mocktoken",
                image="jammy",
                service_token=token,
                lxd_storage_path=GithubRunnerCharm.juju_storage_path,
                charm_state=state,
            ),
        )
        mock_rm.reconcile.assert_called_with(
            5, VirtualMachineResources(cpu=4, memory="7GiB", disk="6GiB")
        )
        mock_rm.reset_mock()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_update_status(self, run, wt, mkdir, rm):
        """
        arrange: reconciliation event timer mocked to be \
          1. active. \
          2. inactive. \
          3. inactive with error thrown for ensure_event_timer.
        act: Emit update_status
        assert:
            1. ensure_event_timer is not called.
            2. ensure_event_timer is called.
            3. Charm throws error.
        """
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url
        mock_rm.download_latest_runner_image = mock_download_latest_runner_image

        harness = Harness(GithubRunnerCharm)

        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()

        event_timer_mock = MagicMock(spec=EventTimer)
        harness.charm._event_timer = event_timer_mock
        event_timer_mock.is_active.return_value = True

        # 1. event timer is active
        harness.charm.on.update_status.emit()
        assert event_timer_mock.ensure_event_timer.call_count == 0
        assert not isinstance(harness.charm.unit.status, BlockedStatus)

        # 2. event timer is not active
        event_timer_mock.is_active.return_value = False
        harness.charm.on.update_status.emit()
        event_timer_mock.ensure_event_timer.assert_called_once()
        assert not isinstance(harness.charm.unit.status, BlockedStatus)

        # 3. ensure_event_timer throws error.
        event_timer_mock.ensure_event_timer.side_effect = TimerEnableError("mock error")
        with pytest.raises(TimerEnableError):
            harness.charm.on.update_status.emit()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_stop(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        harness = Harness(GithubRunnerCharm)
        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()
        harness.charm.on.stop.emit()
        mock_rm.flush.assert_called()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_start_failure(self, run, wt, mkdir, rm):
        """Test various error thrown during install."""
        rm.return_value = mock_rm = MagicMock()
        mock_rm.get_latest_runner_bin_url = mock_get_latest_runner_bin_url

        harness = Harness(GithubRunnerCharm)
        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()

        harness.charm._reconcile_runners = raise_runner_error
        harness.charm.on.start.emit()
        assert harness.charm.unit.status == MaintenanceStatus(
            "Failed to start runners: mock error"
        )

    @patch("charm.RunnerManager")
    @patch("charm.OpenstackRunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_config_changed_openstack_clouds_yaml(self, run, wt, mkdir, orm, rm):
        """
        arrange: Setup mocked charm.
        act: Fire config changed event to use openstack-clouds-yaml.
        assert: Charm is in maintenance state.
        """
        harness = Harness(GithubRunnerCharm)
        cloud_yaml = {
            "clouds": {
                "microstack": {
                    "auth": {
                        "auth_url": secrets.token_hex(16),
                        "project_name": secrets.token_hex(16),
                        "project_domain_name": secrets.token_hex(16),
                        "username": secrets.token_hex(16),
                        "user_domain_name": secrets.token_hex(16),
                        "password": secrets.token_hex(16),
                    }
                }
            }
        }
        harness.update_config(
            {
                PATH_CONFIG_NAME: "mockorg/repo",
                TOKEN_CONFIG_NAME: "mocktoken",
                OPENSTACK_CLOUDS_YAML_CONFIG_NAME: yaml.safe_dump(cloud_yaml),
            }
        )

        harness.begin()

        harness.charm.on.config_changed.emit()

        assert harness.charm.unit.status == MaintenanceStatus()

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action(self, run, wt, mkdir, rm):
        rm.return_value = mock_rm = MagicMock()
        mock_event = MagicMock()

        mock_rm.get_github_info = mock_get_github_info

        harness = Harness(GithubRunnerCharm)
        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.begin()

        harness.charm._on_check_runners_action(mock_event)
        mock_event.set_results.assert_called_with(
            {"online": 2, "offline": 2, "unknown": 1, "runners": "test runner 0, test runner 1"}
        )

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_check_runners_action_with_errors(self, run, wt, mkdir, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        # No config
        harness.charm._on_check_runners_action(mock_event)
        mock_event.fail.assert_called_with("Invalid Github config, Missing path configuration")

    @patch("charm.RunnerManager")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_flush_runners_action(self, run, wt, mkdir, rm):
        mock_event = MagicMock()

        harness = Harness(GithubRunnerCharm)
        harness.begin()

        harness.charm._on_flush_runners_action(mock_event)
        mock_event.fail.assert_called_with("Invalid Github config, Missing path configuration")
        mock_event.reset_mock()

        harness.update_config({PATH_CONFIG_NAME: "mockorg/repo", TOKEN_CONFIG_NAME: "mocktoken"})
        harness.charm._on_flush_runners_action(mock_event)
        mock_event.set_results.assert_called()
        mock_event.reset_mock()
