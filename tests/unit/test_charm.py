# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import secrets
from pathlib import Path
from typing import Type
from unittest.mock import MagicMock, PropertyMock

import ops.testing
import pytest

import charm
from charm import (
    RECONCILE_INTERVAL_CONFIG_NAME,
    RECONCILE_RUNNERS_EVENT,
    CharmConfigInvalidError,
    ConfigurationError,
    FlushMode,
    GithubRunnerCharm,
    GitHubRunnerStatus,
    MissingRunnerBinaryError,
    OpenStackUnauthorizedError,
    ProxyConfig,
    RunnerError,
    RunnerManager,
    RunnerManagerConfig,
    RunnerStorage,
    SubprocessError,
    TokenError,
)
from charm_state import TEST_MODE_CONFIG_NAME
from tests.unit.factories import CharmStateFactory, ProxyConfigFactory, RunnerInfoFactory


@pytest.fixture(name="harness")
def harness_fixture() -> ops.testing.Harness:
    """The mocked charm using harness."""
    harness = ops.testing.Harness(GithubRunnerCharm)
    harness.begin()
    return harness


@pytest.fixture(name="mock_charm")
def mock_charm_fixture(harness: ops.testing.Harness) -> GithubRunnerCharm:
    """The mocked charm using harness."""
    return harness.charm


@pytest.mark.parametrize(
    "error_type, error_message, expected_status",
    [
        pytest.param(
            ConfigurationError,
            "Test Configuration Error",
            ops.BlockedStatus,
            id="configuration_error",
        ),
        pytest.param(TokenError, "Test Token Error", ops.BlockedStatus, id="token_error"),
        pytest.param(
            MissingRunnerBinaryError,
            (
                "GitHub runner application not downloaded; the charm will retry download on "
                "reconcile interval"
            ),
            ops.MaintenanceStatus,
            id="missing_runner_binary_error",
        ),
        pytest.param(
            OpenStackUnauthorizedError,
            "Unauthorized OpenStack connection. Check credentials.",
            ops.BlockedStatus,
            id="openstack_unauthorized_error",
        ),
    ],
)
def test_error_handling(
    error_type: Type[Exception],
    error_message: str,
    expected_status: Type[ops.BlockedStatus | ops.MaintenanceStatus],
    mock_charm: GithubRunnerCharm,
):
    """
    arrange: Mock the charm instance, event instance, and logger. Mock the function to raise the \
        specified error.
    act: Call the decorated function.
    assert: Ensure that the logger is called with the expected message and the charm's unit \
        status is set accordingly.
    """

    @charm.catch_charm_errors
    def mocked_function(*args, **kwargs):
        """Mocked function that raises an error.

        Args:
            args: Positional arguments placeholder.
            kwargs: Keyword arguments placeholder.

        Raises:
            error_type: The specified error.
        """
        raise error_type(error_message)

    mocked_function(mock_charm, MagicMock())

    assert isinstance(mock_charm.unit.status, expected_status)
    assert mock_charm.unit.status == expected_status(error_message)


@pytest.mark.parametrize(
    "error_type, error_message, expected_status",
    [
        pytest.param(
            ConfigurationError,
            "Test Configuration Error",
            ops.BlockedStatus,
            id="configuration_error",
        ),
        pytest.param(
            MissingRunnerBinaryError,
            (
                "GitHub runner application not downloaded; the charm will retry download on "
                "reconcile interval"
            ),
            ops.MaintenanceStatus,
            id="missing_runner_binary_error",
        ),
    ],
)
def test_action_error_handling(
    error_type: Type[Exception],
    error_message: str,
    expected_status: Type[ops.BlockedStatus | ops.MaintenanceStatus],
    mock_charm: GithubRunnerCharm,
):
    """
    arrange: Mock the charm instance, event instance, and logger. Mock the function to raise the \
        specified error.
    act: Call the decorated function.
    assert: Ensure that the logger is called with the expected message, the charm's unit status \
        is set accordingly, and the event is failed with the error message.
    """
    mock_action_event = MagicMock()

    @charm.catch_action_errors
    def mocked_function(*args, **kwargs):
        """Mocked function that raises an error.

        Args:
            args: Positional arguments placeholder.
            kwargs: Keyword arguments placeholder.

        Raises:
            error_type: The specified error.
        """
        raise error_type(error_message)

    mocked_function(mock_charm, mock_action_event)

    assert isinstance(mock_charm.unit.status, expected_status)
    assert mock_charm.unit.status == expected_status(error_message)
    mock_action_event.fail.assert_called_once_with(error_message)


def test_setup_state_invalid_cases(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock CharmState to raise the specified exceptions.
    act: Call _setup_state method.
    assert: Ensure ConfigurationError is raised with the appropriate message.
    """
    monkeypatch.setattr(
        charm.CharmState,
        "from_charm",
        MagicMock(side_effect=CharmConfigInvalidError("Invalid state")),
    )

    with pytest.raises(ConfigurationError) as exc_info:
        mock_charm._setup_state()
    assert "Invalid state" in str(exc_info.value)


def test_create_memory_storage_failure(
    tmp_path: Path, mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock execute_command to simulate an OSError.
    act: When _create_memory_storage is called.
    assert: Ensure RunnerError is raised with the appropriate message.
    """
    monkeypatch.setattr(
        charm,
        "execute_command",
        MagicMock(side_effect=OSError("Failed to execute command")),
    )
    path = tmp_path / "test_storage"
    size = 1024  # 1MB

    with pytest.raises(RunnerError) as exc_info:
        mock_charm._create_memory_storage(path, size)
    assert str(exc_info.value) == "Failed to configure runner storage"


def test_create_memory_storage_mount(
    tmp_path: Path, mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock execute_command to simulate successful mount.
    act: Call _create_memory_storage method with valid path and size.
    assert: Ensure execute_command was called with the correct parameters.
    """
    monkeypatch.setattr(charm, "execute_command", (mock_execute_command := MagicMock()))
    path = tmp_path / "test_storage"
    size = 1024  # 1MB

    mock_charm._create_memory_storage(path, size)

    mock_execute_command.assert_called_once_with(
        ["mount", "-t", "tmpfs", "-o", f"size={size}k", "tmpfs", str(path)]
    )


def test_create_memory_storage_remount(
    tmp_path: Path, mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Create a tmpfs and then mock execute_command to simulate successful remount.
    act: Call _create_memory_storage method again with the same path and size.
    assert: Ensure execute_command was called with the correct parameters for remount.
    """
    monkeypatch.setattr(charm, "execute_command", (mock_execute_command := MagicMock()))
    path = tmp_path / "test_storage"
    size = 1024  # 1MB
    path.mkdir()

    mock_charm._create_memory_storage(path, size)

    mock_execute_command.assert_called_once_with(
        ["mount", "-o", f"remount,size={size}k", str(path)]
    )


def test_ensure_runner_storage_raises_error(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    arrange: Set up the charm instance and monkeypatch shutil.disk_usage method.
    act: Call the _ensure_runner_storage method with size greater than available space.
    assert: Ensure ConfigurationError is raised.
    """
    mock_disk_usage = MagicMock(return_value=PropertyMock(total=1))  # total disk space of 2 GiB
    monkeypatch.setattr(charm.shutil, "disk_usage", mock_disk_usage)
    mock_charm.juju_storage_path = tmp_path / "storage/juju"
    mock_charm.ram_pool_path = tmp_path / "storage/ram"

    with pytest.raises(ConfigurationError):
        mock_charm._ensure_runner_storage(
            2048, RunnerStorage.MEMORY
        )  # Trying to allocate 2 GiB on a 1 GiB disk


@pytest.mark.parametrize(
    "size, runner_storage, expected_path",
    [
        (1024, RunnerStorage.MEMORY, Path("storage/ram")),
        (0, RunnerStorage.MEMORY, Path("storage/ram")),
        (1024, RunnerStorage.JUJU_STORAGE, Path("storage/juju")),
    ],
)
def test_ensure_runner_storage(
    mock_charm: GithubRunnerCharm,
    monkeypatch: pytest.MonkeyPatch,
    size: int,
    runner_storage: RunnerStorage,
    expected_path: Path,
    tmp_path: Path,
):
    """
    arrange: Set up the charm instance and monkeypatch shutil.disk_usage method.
    act: Call the _ensure_runner_storage method with the given arguments.
    assert: Ensure the correct path is returned and that shutil.disk_usage is called with the \
        correct argument.
    """
    mock_disk_usage = MagicMock(return_value=PropertyMock(total=2048 * 1024 * 1024))  # 2GiB
    monkeypatch.setattr(charm.shutil, "disk_usage", mock_disk_usage)
    mock_charm.juju_storage_path = tmp_path / "storage/juju"
    mock_charm.ram_pool_path = tmp_path / "storage/ram"

    path = mock_charm._ensure_runner_storage(size, runner_storage)

    assert path == tmp_path / expected_path


def test_ensure_service_health_active(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up the charm instance and mock the execute_command to return 'active'.
    act: Call the _ensure_service_health method.
    assert: Ensure that no exception is raised.
    """
    monkeypatch.setattr(
        charm, "execute_command", (mock_execute_command := MagicMock(return_value="active"))
    )

    mock_charm._ensure_service_health()

    assert mock_execute_command.called_with(
        ["/usr/bin/systemctl", "is-active", "repo-policy-compliance"]
    )


def test_ensure_service_health_inactive(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up the charm instance and mock the execute_command to raise SubprocessError.
    act: Call the _ensure_service_health method.
    assert: Ensure that SubprocessError is raised and proper commands are executed.
    """
    mock_execute_command = MagicMock(side_effect=SubprocessError([], 1, "", ""))
    monkeypatch.setattr(charm, "execute_command", mock_execute_command)

    with pytest.raises(SubprocessError):
        mock_charm._ensure_service_health()
        assert mock_execute_command.called_with(
            ["/usr/bin/systemctl", "is-active", "repo-policy-compliance"]
        )
        assert mock_execute_command.called_with(
            ["/usr/bin/systemctl", "restart", "repo-policy-compliance"]
        )


def test_get_runner_manager(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up the charm instance, charm state, and mock necessary methods.
    act: Call the _get_runner_manager method with the given arguments.
    assert: Ensure that the correct RunnerManager instance is returned.
    """
    # Mocking necessary methods and attributes
    mock_charm._ensure_service_health = MagicMock()
    mock_charm._ensure_runner_storage = MagicMock(
        return_value="/storage/ram"
    )  # Mocking the return value of _ensure_runner_storage
    test_token = secrets.token_hex(16)
    mock_charm._get_service_token = MagicMock(return_value=test_token)
    mock_charm.service_token = PropertyMock(
        return_value=None
    )  # Mocking the service_token property
    mock_state = CharmStateFactory()
    mock_charm.unit.name = "test_app/0"

    runner_manager = mock_charm._get_runner_manager(mock_state)

    assert runner_manager.app_name == "test_app"
    assert isinstance(runner_manager.config, RunnerManagerConfig)
    assert runner_manager.config.charm_state == mock_state


def test_block_on_openstack_config_enabled(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up the charm instance and mock the charm_config.openstack_clouds_yaml to return a\
         non-None value.
    act: Call the _block_on_openstack_config method
    assert: Ensure that the unit status is set to BlockedStatus and the method returns True
    """
    mock_state = CharmStateFactory()
    mock_state.charm_config.openstack_clouds_yaml = {"non": "empty"}
    monkeypatch.setattr(
        charm,
        "BlockedStatus",
        (block_mock := MagicMock(return_value=ops.BlockedStatus())),
    )

    result = mock_charm._block_on_openstack_config(mock_state)

    assert result is True
    block_mock.assert_called_once()


def test_block_on_openstack_config_disabled(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up the charm instance and mock the charm_config.openstack_clouds_yaml to return \
        None.
    act: Call the _block_on_openstack_config method
    assert: Ensure that the unit status is not set and the method returns False
    """
    mock_state = CharmStateFactory()
    mock_state.charm_config.openstack_clouds_yaml = None
    monkeypatch.setattr(charm.ops, "BlockedStatus", (block_mock := MagicMock()))

    result = mock_charm._block_on_openstack_config(mock_state)

    assert result is False  # Ensure that the method returns False
    block_mock.assert_not_called()


def test_common_install_code_with_openstack(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness
):
    """
    arrange: Set up the charm instance, charm state, and mock necessary methods for OpenStack \
        scenario.
    act: Call the _common_install_code method.
    assert: Ensure that the appropriate methods are called and status is set correctly.
    """
    mock_state = CharmStateFactory()
    mock_state.charm_config.openstack_clouds_yaml = {"non": "empty"}
    # Mocking necessary methods
    monkeypatch.setattr(
        charm, "openstack_manager", (openstack_mock := MagicMock(spec=charm.openstack_manager))
    )
    harness.update_config({TEST_MODE_CONFIG_NAME: "insecure"})
    mock_charm._stored = MagicMock()
    mock_charm._install_deps = MagicMock()
    mock_charm._start_services = MagicMock()
    mock_charm._refresh_firewall = MagicMock()
    mock_charm._get_runner_manager = MagicMock()
    mock_charm._get_runner_manager.return_value.has_runner_image.return_value = False
    mock_charm._set_reconcile_timer = MagicMock()

    result = mock_charm._common_install_code(mock_state)

    assert result is False
    openstack_mock.build_image.assert_called()
    openstack_mock.create_instance_config.assert_called()
    openstack_mock.create_instance.assert_called()


def test_common_install_code_without_openstack(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up the charm instance, charm state, and mock necessary methods for non-OpenStack \
        scenario.
    act: Call the _common_install_code method.
    assert: Ensure that the appropriate methods are called and status is set correctly.
    """
    mock_state = CharmStateFactory()
    mock_state.charm_config.openstack_clouds_yaml = None
    # Mocking necessary methods
    monkeypatch.setattr(charm.metrics, "setup_logrotate", log_rotate_mock := MagicMock())
    mock_charm._stored = MagicMock()
    mock_charm._install_deps = (install_mock := MagicMock())
    mock_charm._start_services = (start_services_mock := MagicMock())
    mock_charm._refresh_firewall = (refresh_firewall_mock := MagicMock())
    mock_charm._get_runner_manager = MagicMock(return_value=(runner_manager_mock := MagicMock()))
    mock_charm._get_runner_manager.return_value.has_runner_image.return_value = False
    mock_charm._set_reconcile_timer = (reconcile_timer_mock := MagicMock())

    result = mock_charm._common_install_code(mock_state)

    assert result is True
    install_mock.assert_called()
    start_services_mock.assert_called()
    log_rotate_mock.assert_called()
    refresh_firewall_mock.assert_called()
    runner_manager_mock.build_runner_image.assert_called()
    runner_manager_mock.schedule_build_runner_image.assert_called()
    runner_manager_mock.get_latest_runner_bin_url.assert_called()
    runner_manager_mock.update_runner_bin.assert_called()
    reconcile_timer_mock.assert_called()


def test__on_install(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _setup_state method and _common_install_code method.
    act: Call _on_install method.
    assert: Verify that _setup_state and _common_install_code methods are called.
    """
    mock_charm._setup_state = (mock_setup_state := MagicMock())
    mock_charm._common_install_code = (mock_common_install_code := MagicMock())

    mock_charm._on_install(MagicMock())

    mock_setup_state.assert_called_once()
    mock_common_install_code.assert_called_once()


def test__on_start(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _setup_state method, _block_on_openstack_config method,\
        _get_runner_manager method, _check_and_update_dependencies method,\
        runner_manager.flush method, and _reconcile_runners method.
    act: Call _on_start method.
    assert: Verify the mocks are called and unit is in ActiveStatus.
    """
    mock_charm._setup_state = (mock_setup_state := MagicMock())
    mock_charm._block_on_openstack_config = (
        mock_block_on_openstack_config := MagicMock(return_value=False)
    )
    mock_charm._get_runner_manager = MagicMock(return_value=(mock_runner_manager := MagicMock()))
    mock_charm._check_and_update_dependencies = (mock_check_and_update_dependencies := MagicMock())
    mock_runner_manager.flush = (mock_runner_manager_flush := MagicMock())
    mock_charm._reconcile_runners = (mock_reconcile_runners := MagicMock())

    mock_charm._on_start(MagicMock())

    mock_setup_state.assert_called_once()
    mock_block_on_openstack_config.assert_called_once()
    mock_check_and_update_dependencies.assert_called_once()
    mock_runner_manager_flush.assert_called_once()
    mock_reconcile_runners.assert_called_once()
    assert mock_charm.unit.status == ops.ActiveStatus()


@pytest.mark.parametrize(
    "reboot_required",
    [
        pytest.param(0, id="required"),
        pytest.param(1, id="not required"),
    ],
)
def test__update_kernel(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch, reboot_required: int
):
    """
    arrange: Set up mock for _apt_install method and execute_command function.
    act: Call _update_kernel method.
    assert: Verify that _apt_install method is called with ["linux-generic"],\
        execute_command is called with ["ls", "/var/run/reboot-required"],\
        and unit.reboot is called when a new version is available.
    """
    monkeypatch.setattr(
        charm,
        "execute_command",
        (mock_execute_command := MagicMock(return_value=("", reboot_required))),
    )
    mock_charm._apt_install = (mock_apt_install := MagicMock())
    mock_charm.unit.reboot = MagicMock()

    mock_charm._update_kernel(now=False)

    mock_apt_install.assert_called_once_with(["linux-generic"])
    mock_execute_command.assert_called_once_with(
        ["ls", "/var/run/reboot-required"], check_exit=False
    )
    if reboot_required == 0:
        mock_charm.unit.reboot.assert_called()


def test__set_reconcile_timer(mock_charm: GithubRunnerCharm, harness: ops.testing.Harness):
    """
    arrange: Set up mock for _event_timer.ensure_event_timer method.
    act: Call _set_reconcile_timer method.
    assert: Verify that _event_timer.ensure_event_timer method is called with the correct \
        arguments.
    """
    mock_charm._event_timer.ensure_event_timer = (mock_ensure_event_timer := MagicMock())
    harness.update_config({RECONCILE_INTERVAL_CONFIG_NAME: 60})

    mock_charm._set_reconcile_timer()

    mock_ensure_event_timer.assert_called_once_with(
        event_name="reconcile-runners",
        interval=60,
        timeout=59,
    )


def test__ensure_reconcile_timer_is_active_timer_is_inactive(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _event_timer.is_active and _set_reconcile_timer methods.
    act: Call _ensure_reconcile_timer_is_active method.
    assert: Verify that _event_timer.is_active is called with the correct event name,\
        and _set_reconcile_timer is called when the timer is not active
    """
    mock_charm._event_timer.is_active = (mock_is_active := MagicMock(return_value=False))
    mock_charm._set_reconcile_timer = (mock_set_reconcile_timer := MagicMock(return_value=False))

    mock_charm._ensure_reconcile_timer_is_active()

    mock_is_active.assert_called_once_with(RECONCILE_RUNNERS_EVENT)
    mock_set_reconcile_timer.assert_called_once()


def test__ensure_reconcile_timer_is_active_timer_is_active(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _event_timer.is_active and _set_reconcile_timer methods.
    act: Call _ensure_reconcile_timer_is_active method.
    assert: Verify that _event_timer.is_active is called with the correct event name,\
        and _set_reconcile_timer is not called when the timer is active.
    """
    mock_charm._event_timer.is_active = (mock_is_active := MagicMock(return_value=True))
    mock_charm._set_reconcile_timer = (mock_set_reconcile_timer := MagicMock())

    mock_charm._ensure_reconcile_timer_is_active()

    mock_is_active.assert_called_once_with(RECONCILE_RUNNERS_EVENT)
    mock_set_reconcile_timer.assert_not_called()


def test__on_upgrade_charm(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _setup_state, _common_install_code, _get_runner_manager,\
        runner_manager.flush, and _reconcile_runners methods.
    act: Call _on_upgrade_charm method.
    assert: Verify that methods are called in the correct order and with the correct arguments.
    """
    mock_charm._setup_state = (mock_setup_state := MagicMock())
    mock_charm._common_install_code = (mock_common_install_code := MagicMock())
    mock_charm._get_runner_manager = MagicMock(return_value=(mock_runner_manager := MagicMock()))
    mock_runner_manager.flush = (mock_runner_manager_flush := MagicMock())
    mock_charm._reconcile_runners = (mock_reconcile_runners := MagicMock())

    mock_charm._on_upgrade_charm(MagicMock())

    mock_setup_state.assert_called_once()
    mock_common_install_code.assert_called_once_with(mock_setup_state.return_value)
    mock_runner_manager_flush.assert_called_once_with(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
    mock_reconcile_runners.assert_called_once()


def test__on_config_changed_reconcile_timer_is_set(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _setup_state and _set_reconcile_timer methods.
    act: Call _on_config_changed method.
    assert: Verify that _setup_state and _set_reconcile_timer methods are called.
    """
    mock_charm._setup_state = MagicMock()
    mock_charm._set_reconcile_timer = MagicMock()

    mock_charm._on_config_changed(MagicMock())

    mock_charm._setup_state.assert_called_once()
    mock_charm._set_reconcile_timer.assert_called_once()


def test__on_config_changed_no_openstack_config(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for _setup_state, _block_on_openstack_config, _get_runner_manager,\
        _refresh_firewall, and _reconcile_runners methods.
    act: Call _on_config_changed method.
    assert: Verify that _setup_state, _block_on_openstack_config, _get_runner_manager,\
        _refresh_firewall, and _reconcile_runners methods are called.
    """
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._set_reconcile_timer = MagicMock()
    mock_charm._block_on_openstack_config = MagicMock(return_value=False)
    mock_charm._get_runner_manager = MagicMock()
    mock_charm._refresh_firewall = MagicMock()
    mock_charm._reconcile_runners = MagicMock()

    mock_charm._on_config_changed(MagicMock())

    mock_charm._setup_state.assert_called_once()
    mock_charm._get_runner_manager.assert_called()
    mock_charm._refresh_firewall.assert_called_once()
    mock_charm._reconcile_runners.assert_called_once()


def test__check_and_update_dependencies_with_updates(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for methods called within _check_and_update_dependencies,\
        and set appropriate return values for those mocks.
    act: Call _check_and_update_dependencies method.
    assert: Verify that methods are called with the correct arguments and return value is True.
    """
    runner_manager = MagicMock(spec=RunnerManager)
    token = "dummy_token"
    proxy_config = MagicMock(spec=ProxyConfig)
    runner_manager.check_runner_bin.return_value = True
    runner_info = PropertyMock(download_url="http://example.com/runner.bin")
    runner_manager.get_latest_runner_bin_url.return_value = runner_info
    mock_charm._install_repo_policy_compliance = (
        mock_install_repo_policy := MagicMock(return_value=True)
    )
    mock_charm._start_services = (mock_start_services := MagicMock())

    result = mock_charm._check_and_update_dependencies(runner_manager, token, proxy_config)

    runner_manager.check_runner_bin.assert_called_once()
    runner_manager.get_latest_runner_bin_url.assert_called_once()
    mock_install_repo_policy.assert_called_once_with(proxy_config)
    runner_manager.update_runner_bin.assert_called_once_with(runner_info)
    runner_manager.flush.assert_called_once_with(FlushMode.FLUSH_IDLE_WAIT_REPO_CHECK)
    mock_start_services.assert_called_once_with(token, proxy_config)
    assert result is True


def test__on_reconcile_runners_with_no_busy_runners(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mock for methods called within _on_reconcile_runners\
        and set appropriate return values for those mocks.
    act: Call _on_reconcile_runners method.
    assert: Verify that methods are called with the correct arguments and unit status is set to \
        ActiveStatus.
    """
    # Mocking necessary objects and methods
    runner_manager = MagicMock(spec=RunnerManager)
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._block_on_openstack_config = MagicMock(return_value=False)
    mock_charm._update_kernel = MagicMock()
    mock_charm._reconcile_runners = MagicMock()
    mock_charm._get_runner_manager = MagicMock(return_value=runner_manager)
    mock_charm._check_and_update_dependencies = MagicMock(return_value=False)
    runner_manager.get_github_info.return_value = [
        PropertyMock(busy=False),
        PropertyMock(busy=False),
        PropertyMock(busy=False),
    ]

    mock_charm._on_reconcile_runners(MagicMock())

    mock_charm._block_on_openstack_config.assert_called_once()
    mock_charm._get_runner_manager.assert_called_once_with(mock_charm._setup_state.return_value)
    mock_charm._check_and_update_dependencies.assert_called_once_with(
        runner_manager, mock_state.charm_config.token, mock_state.proxy_config
    )
    runner_manager.get_github_info.assert_called_once()
    mock_charm._update_kernel.assert_called_once_with(now=True)
    mock_charm._reconcile_runners.assert_called_once_with(
        runner_manager,
        mock_state.runner_config.virtual_machines,
        mock_state.runner_config.virtual_machine_resources,
    )
    assert mock_charm.unit.status == ops.ActiveStatus()


def test__on_check_runners_action(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up a mock for the runner manager and an action event.
    act: Call the _on_check_runners_action method of the charm instance.
    assert: Verify that the action event's fail and set_results methods are called appropriately.
    """
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_runner_manager = MagicMock()
    mock_runner_manager.runner_bin_path = Path("/mock/path/to/runner")
    mock_runner_manager.get_github_info.return_value = [
        RunnerInfoFactory(status=GitHubRunnerStatus.ONLINE.value, name="runner1"),
        RunnerInfoFactory(status=GitHubRunnerStatus.OFFLINE.value, name="runner2"),
        RunnerInfoFactory(status="invalid_status", name="runner3"),
    ]
    mock_charm._get_runner_manager = MagicMock(return_value=mock_runner_manager)
    mock_action_event = MagicMock()

    mock_charm._on_check_runners_action(mock_action_event)

    mock_action_event.fail.assert_not_called()
    mock_action_event.set_results.assert_called_once_with(
        {
            "online": 1,
            "offline": 1,
            "unknown": 1,
            "runners": "runner1",
        }
    )


def test__on_reconcile_runners_action(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mocks for dependencies such as _setup_state, _get_runner_manager, \
        _check_and_update_dependencies, _reconcile_runners, and an action event.
    act: Call the _on_reconcile_runners_action method of the charm instance.
    assert: Verify that the expected methods are called with the correct arguments.
    """
    event = MagicMock()
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._get_runner_manager = MagicMock(return_value=MagicMock())
    mock_charm._check_and_update_dependencies = MagicMock()
    mock_charm._reconcile_runners = MagicMock(return_value={"delta": "mocked_delta"})
    mock_charm._on_check_runners_action = MagicMock()

    mock_charm._on_reconcile_runners_action(event)

    mock_charm._setup_state.assert_called_once()
    mock_charm._get_runner_manager.assert_called_once_with(mock_state)
    mock_charm._check_and_update_dependencies.assert_called_once()
    mock_charm._reconcile_runners.assert_called_once()
    mock_charm._on_check_runners_action.assert_called_once_with(event)
    event.set_results.assert_called_once_with({"delta": "mocked_delta"})


def test__on_flush_runners_action(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mocks for dependencies such as _setup_state, _get_runner_manager, \
        _reconcile_runners, and an action event.
    act: Call the _on_flush_runners_action method of the charm instance.
    assert: Verify that the expected methods are called with the correct arguments.
    """
    event = MagicMock()
    mock_state = CharmStateFactory()
    mock_runner_manager = MagicMock()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._get_runner_manager = MagicMock(return_value=mock_runner_manager)
    mock_charm._reconcile_runners = MagicMock(return_value={"delta": "mocked_delta"})
    mock_charm._on_check_runners_action = MagicMock()

    mock_charm._on_flush_runners_action(event)

    mock_charm._setup_state.assert_called_once()
    mock_charm._get_runner_manager.assert_called_once_with(mock_state)
    mock_runner_manager.flush.assert_called_once_with(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
    mock_charm._reconcile_runners.assert_called_once_with(
        mock_charm._get_runner_manager.return_value,
        mock_state.runner_config.virtual_machines,
        mock_state.runner_config.virtual_machine_resources,
    )
    mock_charm._on_check_runners_action.assert_called_once_with(event)
    event.set_results.assert_called_once_with({"delta": "mocked_delta"})


def test__on_update_dependencies_action(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mocks for dependencies such as _setup_state, _get_runner_manager, \
        _check_and_update_dependencies, and an action event.
    act: Call the _on_update_dependencies_action method of the charm instance.
    assert: Verify that the expected methods are called with the correct arguments.
    """
    event = MagicMock()
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._get_runner_manager = MagicMock(return_value=(runner_manager_mock := MagicMock()))
    mock_charm._check_and_update_dependencies = MagicMock(return_value=True)

    mock_charm._on_update_dependencies_action(event)

    mock_charm._setup_state.assert_called_once()
    mock_charm._get_runner_manager.assert_called_once_with(mock_state)
    mock_charm._check_and_update_dependencies.assert_called_once_with(
        runner_manager_mock,
        mock_state.charm_config.token,
        mock_state.proxy_config,
    )
    event.set_results.assert_called_once_with({"flush": True})


def test__on_update_status(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up a mock for an UpdateStatusEvent.
    act: Call the _on_update_status method of the charm instance.
    assert: Verify that _ensure_reconcile_timer_is_active is called.
    """
    event = MagicMock()
    mock_charm._ensure_reconcile_timer_is_active = (mock_ensure_timer_active := MagicMock())

    mock_charm._on_update_status(event)

    mock_ensure_timer_active.assert_called_once()


def test__on_stop(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mocks for dependencies such as _setup_state, _event_timer, \
        _block_on_openstack_config, _get_runner_manager, and a StopEvent.
    act: Call the _on_stop method of the charm instance.
    assert: Verify that the expected methods are called with the correct arguments.
    """
    event = MagicMock()
    runner_manager_mock = MagicMock()
    mock_charm._setup_state = MagicMock(return_value={})
    mock_charm._event_timer.disable_event_timer = MagicMock()
    mock_charm._block_on_openstack_config = MagicMock(return_value=False)
    mock_charm._get_runner_manager = MagicMock(return_value=runner_manager_mock)

    mock_charm._on_stop(event)

    mock_charm._event_timer.disable_event_timer.assert_called_once_with("reconcile-runners")
    mock_charm._setup_state.assert_called_once()
    mock_charm._block_on_openstack_config.assert_called_once_with({})
    mock_charm._get_runner_manager.assert_called_once_with({})
    runner_manager_mock.flush.assert_called_once_with(FlushMode.FLUSH_BUSY)


def test__reconcile_runners(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up mocks for dependencies such as RunnerManager, VirtualMachineResources.
    act: Call the _reconcile_runners method of the charm instance.
    assert: Verify that the expected methods are called with the correct arguments.
    """
    mocked_runner_manager = MagicMock()
    mocked_virtual_machine_resources = MagicMock()
    monkeypatch.setattr(charm.RunnerManager, "runner_bin_path", MagicMock())

    result = mock_charm._reconcile_runners(
        mocked_runner_manager, 5, mocked_virtual_machine_resources
    )

    mocked_runner_manager.reconcile.assert_called_once_with(5, mocked_virtual_machine_resources)
    assert mock_charm.unit.status == ops.ActiveStatus()
    assert result == {"delta": {"virtual-machines": mocked_runner_manager.reconcile.return_value}}


def test__install_repo_policy_compliance(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up mocks for dependencies such as execute_command and proxy_config.
    act: Call the _install_repo_policy_compliance method of the charm instance.
    assert: Verify expected commands are executed and the correct boolean value is returned.
    """
    monkeypatch.setattr(
        charm,
        "execute_command",
        (
            execute_command_mock := MagicMock(
                side_effect=["Version: 1.0.0", None, "Version: 2.0.0"]
            )
        ),
    )
    mock_proxy_config = ProxyConfigFactory()

    result = mock_charm._install_repo_policy_compliance(mock_proxy_config)

    assert execute_command_mock.call_count == 3
    execute_command_mock.assert_any_call(
        [
            "/usr/bin/python3",
            "-m",
            "pip",
            "show",
            "repo-policy-compliance",
        ],
        check_exit=False,
    )
    execute_command_mock.assert_any_call(
        [
            "/usr/bin/python3",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "git+https://github.com/canonical/repo-policy-compliance@main",
        ],
        env={
            "HTTP_PROXY": mock_proxy_config.http,
            "http_proxy": mock_proxy_config.http,
            "HTTPS_PROXY": mock_proxy_config.https,
            "https_proxy": mock_proxy_config.https,
            "NO_PROXY": mock_proxy_config.no_proxy,
            "no_proxy": mock_proxy_config.no_proxy,
        },
    )
    assert result is True


def test__enable_kernel_modules(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    arrange: Set up mocks for dependencies such as execute_command and patch file operations.
    act: Call the _enable_kernel_modules method of the charm instance.
    assert: Verify expected commands are executed and the kernel module is written to file.
    """
    monkeypatch.setattr(charm, "execute_command", MagicMock())
    mock_charm.kernel_module_path = tmp_path / "tmp_file"

    mock_charm._enable_kernel_modules()

    assert mock_charm.kernel_module_path.read_text(encoding="utf-8") == "br_netfilter\n"


def test__install_deps(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up mocks for dependencies such as execute_command, _setup_state, _apt_install,....
    act: Call the _install_deps method of the charm instance.
    assert: Verify expected commands are executed and the methods are invoked correctly.
    """
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    execute_command_mock = MagicMock()
    monkeypatch.setattr(charm, "execute_command", execute_command_mock)
    mock_charm._apt_install = MagicMock()
    mock_charm._install_repo_policy_compliance = MagicMock()
    mock_charm._enable_kernel_modules = MagicMock()
    monkeypatch.setattr(charm, "LXD_PROFILE_YAML", MagicMock())

    mock_charm._install_deps()

    mock_charm._apt_install.assert_any_call(
        [
            "gunicorn",
            "python3-pip",
            "nftables",
            "cpu-checker",
            "libvirt-clients",
            "libvirt-daemon-driver-qemu",
            "apparmor-utils",
        ]
    )
    execute_command_mock.assert_any_call(
        ["/usr/bin/apt-get", "remove", "-qy", "lxd", "lxd-client"], check_exit=False
    )
    execute_command_mock.assert_any_call(
        ["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"]
    )
    execute_command_mock.assert_any_call(
        ["/usr/bin/snap", "refresh", "lxd", "--channel=latest/stable"]
    )
    execute_command_mock.assert_any_call(["/usr/sbin/usermod", "-aG", "lxd", "ubuntu"])
    execute_command_mock.assert_any_call(["/snap/bin/lxd", "waitready"])
    execute_command_mock.assert_any_call(["/snap/bin/lxd", "init", "--auto"])
    execute_command_mock.assert_any_call(
        ["/snap/bin/lxc", "network", "set", "lxdbr0", "ipv6.address", "none"]
    )
    execute_command_mock.assert_any_call(["/snap/bin/lxd", "waitready"])
    execute_command_mock.assert_any_call(
        [
            "/snap/bin/lxc",
            "profile",
            "device",
            "set",
            "default",
            "eth0",
            "security.ipv4_filtering=true",
            "security.ipv6_filtering=true",
            "security.mac_filtering=true",
            "security.port_isolation=true",
        ]
    )
    mock_charm._apt_install.assert_called_once()
    mock_charm._install_repo_policy_compliance.assert_called_once_with(mock_state.proxy_config)
    assert not mock_charm._enable_kernel_modules.called


def test__start_services(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up mocks for dependencies such as execute_command, os.makedirs, shutil.copyfile, \
        and patch jinja2 environment.
    act: Call the _start_services method of the charm instance.
    assert: Verify that the expected commands are executed and the methods are invoked correctly.
    """
    execute_command_mock = MagicMock()
    monkeypatch.setattr(charm, "execute_command", execute_command_mock)
    monkeypatch.setattr(charm.os, "makedirs", MagicMock())
    monkeypatch.setattr(charm.shutil, "copyfile", MagicMock())
    repo_check_systemd_service_mock = MagicMock()
    monkeypatch.setattr(
        charm.GithubRunnerCharm, "repo_check_systemd_service", repo_check_systemd_service_mock
    )
    mock_charm._get_service_token = MagicMock(return_value="charm_token")
    jinja2_environment_mock = MagicMock()
    jinja2_environment_mock.return_value.get_template.return_value.render.return_value = (
        "service_content"
    )
    monkeypatch.setattr(charm.jinja2, "Environment", jinja2_environment_mock)

    mock_charm._start_services("github_token", MagicMock())

    execute_command_mock.assert_any_call(["/usr/bin/systemctl", "daemon-reload"])
    execute_command_mock.assert_any_call(
        ["/usr/bin/systemctl", "restart", "repo-policy-compliance"]
    )
    execute_command_mock.assert_any_call(
        ["/usr/bin/systemctl", "enable", "repo-policy-compliance"]
    )
    mock_charm._get_service_token.assert_called_once()
    jinja2_environment_mock.assert_called_once()
    assert repo_check_systemd_service_mock.write_text.called_with(
        "service_content", encoding="utf-8"
    )


def test__get_service_token(
    mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    arrange: Set up mocks for dependencies such as logger and patch file operations.
    act: Call the _get_service_token method of the charm instance.
    assert: Verify that the token is generated or read from the file, and the file is written if \
        it doesn't exist.
    """
    mock_service_token_path = tmp_path / "token_path"
    mock_charm.service_token_path = mock_service_token_path
    monkeypatch.setattr(charm.secrets, "token_hex", MagicMock(return_value="testing-token"))

    token = mock_charm._get_service_token()

    assert token == "testing-token"
    assert mock_service_token_path.read_text(encoding="utf-8") == "testing-token"


def test__refresh_firewall(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up mocks for dependenciesexecute_command, FirewallEntry, and Firewall.
    act: Call the _refresh_firewall method of the charm instance.
    assert: Verify that the appropriate commands are executed, and the methods are invoked \
        correctly.
    """
    execute_command_mock = MagicMock()
    monkeypatch.setattr(charm, "execute_command", execute_command_mock)
    firewall_mock = MagicMock()
    monkeypatch.setattr(charm, "Firewall", firewall_mock)
    mock_state = CharmStateFactory()

    mock_charm._refresh_firewall(mock_state)

    firewall_mock.assert_called_once_with("lxdbr0")
    firewall_mock.return_value.refresh_firewall.assert_called_once()


def test__apt_install(mock_charm: GithubRunnerCharm, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up mocks for dependencies such as execute_command.
    act: Call the _apt_install method of the charm instance.
    assert: Verify that the expected apt commands are executed.
    """
    execute_command_mock = MagicMock(return_value=(0, 0))
    monkeypatch.setattr(charm, "execute_command", execute_command_mock)

    mock_charm._apt_install(["package1", "package2"])

    execute_command_mock.assert_any_call(["/usr/bin/apt-get", "update"])
    execute_command_mock.assert_any_call(
        ["/usr/bin/apt-get", "install", "-qy", "package1", "package2"], check_exit=False
    )


def test__on_debug_ssh_relation_changed(mock_charm: GithubRunnerCharm):
    """
    arrange: Set up mocks for dependencies such as _setup_state, _refresh_firewall, \
        _get_runner_manager, runner_manager.flush, and _reconcile_runners.
    act: Call the _on_debug_ssh_relation_changed method of the charm instance.
    assert: Verify that the methods are invoked correctly.
    """
    mock_state = CharmStateFactory()
    mock_charm._setup_state = MagicMock(return_value=mock_state)
    mock_charm._refresh_firewall = MagicMock()
    mock_charm._reconcile_runners = MagicMock()
    mock_runner_manager = MagicMock()
    mock_charm._get_runner_manager = MagicMock(return_value=mock_runner_manager)

    mock_charm._on_debug_ssh_relation_changed(MagicMock())

    mock_charm._refresh_firewall.assert_called_once_with(mock_state)
    mock_charm._get_runner_manager.assert_called_once_with(mock_state)
    mock_charm._reconcile_runners.assert_called_once_with(
        mock_runner_manager,
        mock_state.runner_config.virtual_machines,
        mock_state.runner_config.virtual_machine_resources,
    )
