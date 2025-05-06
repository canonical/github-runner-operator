# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for GithubRunnerCharm."""
import os
import secrets
import typing
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
import yaml
from github_runner_manager.errors import ReconcileError
from github_runner_manager.manager.runner_manager import FlushMode
from github_runner_manager.manager.runner_scaler import RunnerScaler
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, StatusBase, WaitingStatus
from ops.testing import Harness

from charm import (
    ACTIVE_STATUS_RECONCILIATION_FAILED_MSG,
    FAILED_RECONCILE_ACTION_ERR_MSG,
    GithubRunnerCharm,
    catch_action_errors,
    catch_charm_errors,
)
from charm_state import (
    FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME,
    IMAGE_INTEGRATION_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    PATH_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    Arch,
    OpenStackCloudsYAML,
    OpenstackImage,
)
from errors import (
    ConfigurationError,
    LogrotateSetupError,
    MissingMongoDBError,
    RunnerError,
    SubprocessError,
    TokenError,
)
from event_timer import EventTimer, TimerEnableError

TEST_PROXY_SERVER_URL = "http://proxy.server:1234"


@pytest.fixture(name="mock_side_effects", scope="function")
def side_effect_fixture(monkeypatch, tmpdir):
    monkeypatch.setattr("charm.pathlib.Path.mkdir", MagicMock())
    monkeypatch.setattr("charm.pathlib.Path.write_text", MagicMock())
    monkeypatch.setattr("charm.execute_command", MagicMock())
    monkeypatch.setattr("manager_service.yaml_safe_dump", MagicMock())
    monkeypatch.setattr("manager_service.Path.expanduser", lambda x: tmpdir)
    monkeypatch.setattr("manager_service.systemd", MagicMock())


@pytest.fixture(name="mock_manager_service")
def mock_manager_service_fixture(monkeypatch):
    mock_manager_service = MagicMock()
    monkeypatch.setattr("charm.manager_service", mock_manager_service)
    return mock_manager_service


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


def setup_charm_harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    """Setup harness with patched runner manager methods.

    Args:
        monkeypatch: Instance of pytest monkeypatch for patching RunnerManager methods.

    Returns:
        Harness with patched RunnerManager instance.
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
                },
                "region_name": secrets.token_hex(16),
            }
        }
    }
    harness.update_config(
        {
            PATH_CONFIG_NAME: "mock/repo",
            TOKEN_CONFIG_NAME: "mocktoken",
            OPENSTACK_CLOUDS_YAML_CONFIG_NAME: yaml.safe_dump(cloud_yaml),
            OPENSTACK_FLAVOR_CONFIG_NAME: "m1.builder",
            FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME: "",
        }
    )
    harness.begin()
    monkeypatch.setattr("charm.EventTimer.ensure_event_timer", MagicMock())
    monkeypatch.setattr("charm.logrotate.setup", MagicMock())
    return harness


@pytest.fixture(name="harness")
def harness_fixture(monkeypatch) -> Harness:
    return setup_charm_harness(monkeypatch)


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
    hook: str,
    harness: Harness,
    exec_command: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_manager_service,
):
    """
    arrange: Set up charm.
    act: Fire install/upgrade event.
    assert: Common install commands are run on the mock.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    monkeypatch.setattr("charm.logrotate.setup", setup_logrotate := MagicMock())
    event_timer_mock = MagicMock(spec=EventTimer)
    harness.charm._event_timer = event_timer_mock

    getattr(harness.charm.on, hook).emit()

    setup_logrotate.assert_called_once()


def test_on_config_changed_failure(harness: Harness):
    """
    arrange: Set up charm.
    act: Fire config changed event to use aproxy without configured http proxy.
    assert: Charm is in blocked state.
    """
    harness.update_config({USE_APROXY_CONFIG_NAME: True})

    assert isinstance(harness.charm.unit.status, BlockedStatus)
    assert "Invalid proxy configuration" in harness.charm.unit.status.message


def test_on_flush_runners_reconcile_error_fail(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up charm with Openstack mode and ReconcileError.
    act: Run flush runner action.
    assert: Action fails with generic message and goes in ActiveStatus.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    runner_scaler_mock = MagicMock(spec=RunnerScaler)
    runner_scaler_mock.reconcile.side_effect = ReconcileError("mock error")
    monkeypatch.setattr("charm.create_runner_scaler", MagicMock(return_value=runner_scaler_mock))

    mock_event = MagicMock()
    harness.charm._on_flush_runners_action(mock_event)
    mock_event.fail.assert_called_with(FAILED_RECONCILE_ACTION_ERR_MSG)
    assert harness.charm.unit.status.name == ActiveStatus.name
    assert harness.charm.unit.status.message == ACTIVE_STATUS_RECONCILIATION_FAILED_MSG


def test_on_reconcile_runners_action_reconcile_error_fail(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Set up charm with Openstack mode, ready image, and ReconcileError.
    act: Run reconcile runners action.
    assert: Action fails with generic message and goes in ActiveStatus
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    runner_scaler_mock = MagicMock(spec=RunnerScaler)
    runner_scaler_mock.reconcile.side_effect = ReconcileError("mock error")
    monkeypatch.setattr("charm.create_runner_scaler", MagicMock(return_value=runner_scaler_mock))
    monkeypatch.setattr(
        OpenstackImage,
        "from_charm",
        MagicMock(return_value=OpenstackImage(id="test", tags=["test"])),
    )

    mock_event = MagicMock()
    harness.charm._on_reconcile_runners_action(mock_event)

    mock_event.fail.assert_called_with(FAILED_RECONCILE_ACTION_ERR_MSG)
    assert harness.charm.unit.status.name == ActiveStatus.name
    assert harness.charm.unit.status.message == ACTIVE_STATUS_RECONCILIATION_FAILED_MSG


def test_on_reconcile_runners_reconcile_error(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up charm with Openstack mode, ready image, and ReconcileError.
    act: Trigger reconcile_runners event.
    assert: Unit goes into ActiveStatus with error message.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    runner_scaler_mock = MagicMock(spec=RunnerScaler)
    runner_scaler_mock.reconcile.side_effect = ReconcileError("mock error")
    monkeypatch.setattr("charm.create_runner_scaler", MagicMock(return_value=runner_scaler_mock))
    monkeypatch.setattr(
        OpenstackImage,
        "from_charm",
        MagicMock(return_value=OpenstackImage(id="test", tags=["test"])),
    )

    mock_event = MagicMock()
    harness.charm._on_reconcile_runners(mock_event)

    assert harness.charm.unit.status.name == ActiveStatus.name
    assert harness.charm.unit.status.message == ACTIVE_STATUS_RECONCILIATION_FAILED_MSG


def test_on_stop_busy_flush(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up charm with Openstack mode and runner scaler mock.
    act: Trigger stop event.
    assert: Runner scaler mock flushes the runners using busy mode.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    runner_scaler_mock = MagicMock(spec=RunnerScaler)
    monkeypatch.setattr("charm.create_runner_scaler", MagicMock(return_value=runner_scaler_mock))
    mock_event = MagicMock()

    harness.charm._on_stop(mock_event)

    runner_scaler_mock.flush.assert_called_once_with(FlushMode.FLUSH_BUSY)


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("install", id="Install"),
        pytest.param("upgrade_charm", id="Upgrade"),
    ],
)
def test_on_install_failure(
    hook: str, harness: Harness, monkeypatch: pytest.MonkeyPatch, mock_manager_service
):
    """
    arrange: Charm with mock setup_logrotate.
    act:
        1. Mock setup_logrotate fails.
        2. Mock _install_deps raises error.
    assert: Charm goes into error state in both cases.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)
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


def test_charm_goes_into_waiting_state_on_missing_integration_data(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
):
    """
    arrange: Mock charm._setup_state to raise an MissingIntegrationDataError.
    act: Fire config changed event.
    assert: Charm is in blocked state.
    """
    setup_state_mock = MagicMock(side_effect=MissingMongoDBError("mock error"))
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
    reconciliation_mock = MagicMock()
    relation_mock = MagicMock()
    relation_mock.name = "mongodb"
    relation_mock.id = 0
    monkeypatch.setattr("charm.GithubRunnerCharm._trigger_reconciliation", reconciliation_mock)
    getattr(harness.charm.database.on, hook).emit(relation=relation_mock)
    reconciliation_mock.assert_called_once()


# New tests should not be added here. This should be refactored to pytest over time.
# New test should be written with pytest, similar to the above tests.
# Consider to rewrite test with pytest if the tests below needs to be changed.
class TestCharm(unittest.TestCase):
    """Test the GithubRunner charm."""

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("subprocess.run")
    def test_on_update_status(self, run, wt, mkdir):
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


def test_check_runners_action_with_errors():
    mock_event = MagicMock()

    harness = Harness(GithubRunnerCharm)
    harness.begin()

    # No config
    harness.charm._on_check_runners_action(mock_event)
    mock_event.fail.assert_called_with(
        "Failed check runner request: Failed request due to connection failure"
    )


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        pytest.param(ConfigurationError, BlockedStatus, id="charm config error"),
        pytest.param(TokenError, BlockedStatus, id="github token error"),
    ],
)
def test_catch_charm_errors(
    exception: typing.Type[Exception], expected_status: typing.Type[StatusBase]
):
    """
    arrange: given mock charm event handler decorated with catch_charm_errors that raises error.
    act: when charm event is fired.
    assert: the charm is put into expected status.
    """

    class TestCharm:
        """Test charm."""

        def __init__(self):
            """Initialize the test charm."""
            self.unit = MagicMock()

        @catch_charm_errors
        def test_event_handler(self, _: typing.Any):
            """Test event handler.

            Args:
                event: The mock event.

            Raises:
                exception: The testing exception.
            """
            raise exception

    test_charm = TestCharm()

    test_charm.test_event_handler(MagicMock())

    assert isinstance(test_charm.unit.status, expected_status)


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        pytest.param(ConfigurationError, BlockedStatus, id="charm config error"),
    ],
)
def test_catch_action_errors(
    exception: typing.Type[Exception], expected_status: typing.Type[StatusBase]
):
    """
    arrange: given mock charm event handler decorated with catch_charm_errors that raises error.
    act: when charm event is fired.
    assert: the charm is put into expected status.
    """

    class TestCharm:
        """Test charm."""

        def __init__(self):
            """Initialize the test charm."""
            self.unit = MagicMock()

        @catch_action_errors
        def test_event_handler(self, _: typing.Any):
            """Test event handler.

            Args:
                event: The mock event.

            Raises:
                exception: The testing exception.
            """
            raise exception

    test_charm = TestCharm()

    test_charm.test_event_handler(event_mock := MagicMock())

    assert isinstance(test_charm.unit.status, expected_status)
    event_mock.fail.assert_called_once()


@pytest.mark.parametrize(
    "openstack_image, expected_status, expected_value",
    [
        pytest.param(None, BlockedStatus, False, id="Image integration missing."),
        pytest.param(
            OpenstackImage(id=None, tags=None), WaitingStatus, False, id="Image not ready."
        ),
        pytest.param(
            OpenstackImage(id="test", tags=["test"]),
            MaintenanceStatus,
            True,
            id="Valid image integration.",
        ),
    ],
)
def test_openstack_image_ready_status(
    monkeypatch: pytest.MonkeyPatch,
    openstack_image: OpenstackImage | None,
    expected_status: typing.Type[StatusBase],
    expected_value: bool,
):
    """
    arrange: given a monkeypatched OpenstackImage.from_charm that returns different values.
    act: when _get_set_image_ready_status is called.
    assert: expected unit status is set and expected value is returned.
    """
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock(return_value=openstack_image))
    harness = Harness(GithubRunnerCharm)
    harness.begin()

    is_ready = harness.charm._get_set_image_ready_status()

    assert isinstance(harness.charm.unit.status, expected_status)
    assert is_ready == expected_value


def test__on_image_relation_image_not_ready():
    """
    arrange: given a charm with OpenStack instance type and a monkeypatched \
        _get_set_image_ready_status that returns False denoting image not ready.
    act: when _on_image_relation_changed is called.
    assert: nothing happens since _get_set_image_ready_status should take care of status set.
    """
    harness = Harness(GithubRunnerCharm)
    harness.begin()
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    harness.charm._get_set_image_ready_status = MagicMock(return_value=False)

    harness.charm._on_image_relation_changed(MagicMock())

    # the unit is in maintenance status since nothing has happened.
    assert harness.charm.unit.status.name == MaintenanceStatus.name


def test__on_image_relation_image_ready(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm with OpenStack instance type and a monkeypatched \
        _get_set_image_ready_status that returns True denoting image ready.
    act: when _on_image_relation_changed is called.
    assert: runner flush and reconcile is called.
    """
    harness = Harness(GithubRunnerCharm)
    harness.begin()
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    harness.charm._get_set_image_ready_status = MagicMock(return_value=True)
    runner_scaler_mock = MagicMock()
    monkeypatch.setattr("charm.create_runner_scaler", MagicMock(return_value=runner_scaler_mock))

    harness.charm._on_image_relation_changed(MagicMock())

    assert harness.charm.unit.status.name == ActiveStatus.name
    runner_scaler_mock.flush.assert_called_once()
    runner_scaler_mock.reconcile.assert_called_once()


def test__on_image_relation_joined():
    """
    arrange: given an OpenStack mode charm.
    act: when _on_image_relation_joined is fired.
    assert: the relation data is populated with openstack creds.
    """
    harness = Harness(GithubRunnerCharm)
    relation_id = harness.add_relation(IMAGE_INTEGRATION_NAME, "image-builder")
    harness.add_relation_unit(relation_id, "image-builder/0")
    harness.begin()
    state_mock = MagicMock()
    state_mock.charm_config.openstack_clouds_yaml = OpenStackCloudsYAML(
        clouds={
            "test-cloud": {
                "auth": (
                    test_auth_data := {
                        "auth_url": "http://test-auth.url",
                        "password": secrets.token_hex(16),
                        "project_domain_name": "Default",
                        "project_name": "test-project-name",
                        "user_domain_name": "Default",
                        "username": "test-user-name",
                    }
                )
            }
        }
    )
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    harness.charm._on_image_relation_joined(MagicMock())

    assert harness.get_relation_data(relation_id, harness.charm.unit) == test_auth_data


def test_on_config_changed_openstack_clouds_yaml(mock_side_effects):
    """
    arrange: Setup mocked charm.
    act: Fire config changed event to use openstack-clouds-yaml.
    assert: Charm is in blocked state.
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
                },
                "region_name": secrets.token_hex(16),
            }
        }
    }
    harness.update_config(
        {
            PATH_CONFIG_NAME: "mockorg/repo",
            TOKEN_CONFIG_NAME: "mocktoken",
            OPENSTACK_CLOUDS_YAML_CONFIG_NAME: yaml.safe_dump(cloud_yaml),
            OPENSTACK_FLAVOR_CONFIG_NAME: "m1.big",
        }
    )

    harness.begin()

    harness.charm.on.config_changed.emit()

    assert harness.charm.unit.status == BlockedStatus("Please provide image integration.")
