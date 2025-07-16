# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for GithubRunnerCharm."""
import os
import secrets
import typing
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import yaml
from github_runner_manager import constants
from github_runner_manager.platform.platform_provider import TokenError
from ops.model import BlockedStatus, StatusBase, WaitingStatus
from ops.testing import Harness

from charm import (
    LEGACY_RECONCILE_SERVICE,
    LEGACY_RECONCILE_TIMER_SERVICE,
    GithubRunnerCharm,
    catch_action_errors,
    catch_charm_errors,
)
from charm_state import (
    FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME,
    IMAGE_INTEGRATION_NAME,
    LABELS_CONFIG_NAME,
    MONGO_DB_INTEGRATION_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    PATH_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    OpenStackCloudsYAML,
    OpenstackImage,
)
from errors import (
    ConfigurationError,
    ImageIntegrationMissingError,
    ImageNotFoundError,
    LogrotateSetupError,
    MissingMongoDBError,
    RunnerError,
    SubprocessError,
)
from manager_client import GitHubRunnerManagerClient

TEST_PROXY_SERVER_URL = "http://proxy.server:1234"


@pytest.fixture(name="mock_side_effects", scope="function")
def side_effect_fixture(monkeypatch, tmpdir):
    monkeypatch.setattr("charm.pathlib.Path.mkdir", MagicMock())
    monkeypatch.setattr("charm.pathlib.Path.write_text", MagicMock())
    monkeypatch.setattr("charm.execute_command", MagicMock())
    monkeypatch.setattr("charm.systemd", MagicMock())
    monkeypatch.setattr("manager_service.yaml_safe_dump", MagicMock())
    monkeypatch.setattr("manager_service.Path.expanduser", lambda x: tmpdir)
    monkeypatch.setattr("manager_service.Path.mkdir", MagicMock())
    monkeypatch.setattr("manager_service.Path.touch", MagicMock())
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


def mock_get_latest_runner_bin_url(os_name: str = "linux"):
    """Stub function to return test runner_bin_url data.

    Args:
        os_name: OS name placeholder argument.

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
    monkeypatch.setattr("charm.systemd", MagicMock())

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


@pytest.mark.parametrize(
    "config_option",
    [
        pytest.param(PATH_CONFIG_NAME, id="Path"),
        pytest.param(TOKEN_CONFIG_NAME, id="Token"),
        pytest.param(LABELS_CONFIG_NAME, id="Labels"),
    ],
)
def test__on_config_changed_flush(monkeypatch: pytest.MonkeyPatch, config_option: str):
    """
    arrange: given a charm with OpenStack instance type and a certain config option value.
    act: update the config option.
    assert: runner flush is called.
    """
    harness = Harness(GithubRunnerCharm)
    harness.update_config({config_option: secrets.token_hex(16)})
    harness.begin()
    state_mock = MagicMock()
    monkeypatch.setattr("charm.manager_service", MagicMock())
    harness.charm._manager_client = MagicMock(spec=GitHubRunnerManagerClient)
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    harness.charm._check_image_ready = MagicMock(return_value=True)

    harness.update_config({config_option: secrets.token_hex(16)})

    harness.charm._manager_client.flush_runner.assert_called_once()


@pytest.mark.parametrize(
    "config_option",
    [
        pytest.param(PATH_CONFIG_NAME, id="Path"),
        pytest.param(TOKEN_CONFIG_NAME, id="Token"),
        pytest.param(LABELS_CONFIG_NAME, id="Labels"),
    ],
)
def test__on_config_changed_no_flush(monkeypatch: pytest.MonkeyPatch, config_option: str):
    """
    arrange: given a charm with OpenStack instance type and a certain config option value.
    act: update the config option to be the same as before.
    assert: runner flush is called.
    """
    config_option_val = secrets.token_hex(16)
    harness = Harness(GithubRunnerCharm)
    harness.update_config({config_option: config_option_val})
    harness.begin()
    state_mock = MagicMock()
    monkeypatch.setattr("charm.manager_service", MagicMock())
    harness.charm._manager_client = MagicMock(spec=GitHubRunnerManagerClient)
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    harness.charm._check_image_ready = MagicMock(return_value=True)

    harness.update_config({config_option: config_option_val})

    harness.charm._manager_client.flush_runner.assert_not_called()


def test_on_stop_busy_flush_and_stop_service(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Set up charm with Openstack mode and runner scaler mock.
    act: Trigger stop event.
    assert: Runner scaler mock flushes the runners using busy mode.
    """
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    manager_client_mock = MagicMock(spec=GitHubRunnerManagerClient)
    harness.charm._manager_client = manager_client_mock
    mock_manager_service = MagicMock()
    monkeypatch.setattr("charm.manager_service", mock_manager_service)
    mock_event = MagicMock()

    harness.charm._on_stop(mock_event)

    manager_client_mock.flush_runner.assert_called_once_with(busy=True)
    mock_manager_service.stop.assert_called_once()


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
    monkeypatch.setattr("charm.systemd", MagicMock())

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


def test_check_runners_action_with_errors():
    mock_event = MagicMock()

    harness = Harness(GithubRunnerCharm)
    harness.begin()
    harness.charm._manager_client.wait_till_ready = MagicMock()

    # No config
    harness.charm._on_check_runners_action(mock_event)
    mock_event.fail.assert_called_with(
        "Failed runner manager request: Failed request due to connection failure"
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
    "openstack_image, error",
    [
        pytest.param(None, ImageIntegrationMissingError, id="Image integration missing."),
        pytest.param(
            OpenstackImage(id=None, tags=None), ImageNotFoundError, id="Image not ready."
        ),
        pytest.param(
            OpenstackImage(id="test", tags=["test"]),
            None,
            id="Valid image integration.",
        ),
    ],
)
def test_openstack_image_ready_status(
    monkeypatch: pytest.MonkeyPatch,
    openstack_image: OpenstackImage | None,
    error: typing.Type[Exception] | None,
):
    """
    arrange: given a monkeypatched OpenstackImage.from_charm that returns different values.
    act: when _get_set_image_ready_status is called.
    assert: expected unit status is set and expected value is returned.
    """
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock(return_value=openstack_image))
    harness = Harness(GithubRunnerCharm)
    harness.begin()

    if error is None:
        harness.charm._check_image_ready()
        return

    with pytest.raises(error):
        harness.charm._check_image_ready()


def test__on_image_relation_image_not_ready(monkeypatch):
    """
    arrange: given a charm with OpenStack instance type and a monkeypatched \
        with no image integration.
    act: when _on_image_relation_changed is called.
    assert: nothing happens since _get_set_image_ready_status should take care of status set.
    """
    harness = Harness(GithubRunnerCharm)
    harness.begin()
    state_mock = MagicMock()
    harness.charm._setup_state = MagicMock(return_value=state_mock)

    harness.charm._on_image_relation_changed(MagicMock())

    # the unit is in maintenance status since nothing has happened.
    assert harness.charm.unit.status.name == BlockedStatus.name


def test__on_image_relation_image_ready(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm with OpenStack instance type and a monkeypatched \
        _get_set_image_ready_status that returns True denoting image ready.
    act: when _on_image_relation_changed is called.
    assert: runner flush is called.
    """
    harness = Harness(GithubRunnerCharm)
    harness.begin()
    state_mock = MagicMock()
    monkeypatch.setattr("charm.manager_service", MagicMock())
    harness.charm._manager_client = MagicMock(spec=GitHubRunnerManagerClient)
    harness.charm._setup_state = MagicMock(return_value=state_mock)
    harness.charm._check_image_ready = MagicMock(return_value=True)

    harness.charm._on_image_relation_changed(MagicMock())

    harness.charm._manager_client.flush_runner.assert_called_once()


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


def test_metric_log_ownership_for_upgrade(
    harness: Harness, mock_side_effects, tmp_path: Path, monkeypatch
):
    """
    arrange: Metric log exists.
    act: Upgrade charm.
    assert: Call to change the metric ownership is called.

    For context, older revision the metric log is owned by root.
    The current revision the metric log is owned by the runner manager.
    This is to test on upgrade the charm ensures the log file has the correct owner.
    """
    harness.charm._setup_state = MagicMock()

    mock_metric_log_path = tmp_path
    mock_metric_log_path.touch(exist_ok=True)
    monkeypatch.setattr("charm.METRICS_LOG_PATH", mock_metric_log_path)
    monkeypatch.setattr("charm.shutil", shutil_mock := MagicMock())
    monkeypatch.setattr("charm.execute_command", MagicMock(return_value=(0, "Mock_stdout")))

    harness.charm.on.upgrade_charm.emit()

    shutil_mock.chown.assert_called_once_with(
        mock_metric_log_path,
        user=constants.RUNNER_MANAGER_USER,
        group=constants.RUNNER_MANAGER_GROUP,
    )


def test_attempting_disable_legacy_service_for_upgrade(
    harness: Harness, mock_side_effects, monkeypatch
):
    """
    arrange: None.
    act: Upgrade charm.
    assert: Calls to stop the legacy service is performed.
    """
    harness.charm._setup_state = MagicMock()
    monkeypatch.setattr("charm.systemd", mock_systemd := MagicMock())
    monkeypatch.setattr("charm.execute_command", MagicMock(return_value=(0, "Mock_stdout")))
    monkeypatch.setattr("charm.pathlib", MagicMock())

    harness.charm.on.upgrade_charm.emit()

    mock_systemd.service_disable.assert_has_calls(
        [mock.call(LEGACY_RECONCILE_TIMER_SERVICE), mock.call(LEGACY_RECONCILE_SERVICE)],
        any_order=True,
    )
    mock_systemd.service_stop.assert_has_calls(
        [mock.call(LEGACY_RECONCILE_TIMER_SERVICE), mock.call(LEGACY_RECONCILE_SERVICE)],
        any_order=True,
    )


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("database_created", id="Database Created"),
        pytest.param("endpoints_changed", id="Endpoints Changed"),
        pytest.param("mongodb_relation_broken", id="MongoDB Relation Departed"),
    ],
)
def test_database_integration_events_setup_service(
    hook: str, monkeypatch: pytest.MonkeyPatch, harness: Harness
):
    """
    arrange: Mock charm._setup_service.
    act: Fire mongodb relation events.
    assert: _setup_service has been called.
    """
    setup_service_mock = MagicMock()
    relation_mock = MagicMock()
    relation_mock.name = "mongodb"
    relation_mock.id = 0
    monkeypatch.setattr("charm.GithubRunnerCharm._setup_service", setup_service_mock)
    if hook.startswith(MONGO_DB_INTEGRATION_NAME):
        getattr(harness.charm.on, hook).emit(relation=relation_mock)
    else:
        getattr(harness.charm.database.on, hook).emit(relation=relation_mock)
    setup_service_mock.assert_called_once()
