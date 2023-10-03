#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import logging
from typing import Generator
from unittest.mock import MagicMock, Mock

import pytest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from ops import CharmBase
from ops.testing import Harness
from pydantic import ValidationError

import cos
from charm_state import ProxyConfig, State
from event_timer import EventTimer
from promtail import Config, PromtailDownloadInfo

TEST_PROMTAIL_BINARY_ZIP_INFO = {
    "url": "http://promtail/promtail-linux-amd64.zip",
    "zipsha": "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447",
    "binsha": "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447",
}
TEST_REMOTE_APP = "loki"
TEST_PLATFORM = "x86_64"
TEST_PROMTAIL_PLATFORM = "amd64"  # x86_64 is translated to amd64


class FakeCharm(CharmBase):
    """Fake charm for testing.

    We only need to instantiate the charm to test the observer.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = State.from_charm()
        self.cos_observer = cos.Observer(self, self.state)


@pytest.fixture(name="harness")
def harness_fixture() -> Generator[Harness, None, None]:
    """Enable ops test framework harness."""
    harness = Harness(
        FakeCharm,
        meta="""
      name: test-app
      requires:
        metrics-logging:
          interface: loki_push_api
      """,
    )
    yield harness
    harness.cleanup()


@pytest.fixture(autouse=True, name="promtail")
def patched_promtail_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Patch promtail module.

    Preserve Config and PromtailDownloadInfo classes in order to be testable.
    """
    mock_promtail = MagicMock()
    monkeypatch.setattr("cos.promtail", mock_promtail)
    mock_promtail.Config = Config
    mock_promtail.PromtailDownloadInfo = PromtailDownloadInfo
    return mock_promtail


@pytest.fixture(autouse=True, name="event_timer")
def patched_event_timer_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Patch EventTimer class."""
    mock_event_timer = MagicMock(EventTimer, autospec=True)
    monkeypatch.setattr("cos.EventTimer", mock_event_timer)
    return mock_event_timer


@pytest.fixture(autouse=True, name="platform")
def patched_platform_fixture(monkeypatch: MonkeyPatch) -> MagicMock:
    """Patch platform.processor to return the test platform.

    We need to patch this because platform.processor uses a cache internally,
    and depending on the order of the tests, a mock would be returned
    (e.g. if test_charm is executed before test_cos).
    """
    mock_promtail_arch = MagicMock(return_value=TEST_PLATFORM)
    monkeypatch.setattr("cos.platform.processor", mock_promtail_arch)
    return mock_promtail_arch


def _update_integration_with_promtail_binary(harness: Harness, integration_id: int) -> None:
    """Update integration with promtail binary info.

    Args:
        harness: The harness to update the integration on.
        integration_id: The integration id.
    """
    harness.update_relation_data(
        integration_id,
        TEST_REMOTE_APP,
        {
            "promtail_binary_zip_url": json.dumps(
                {TEST_PROMTAIL_PLATFORM: TEST_PROMTAIL_BINARY_ZIP_INFO}
            )
        },
    )


def _update_integration_data_with_endpoint(harness: Harness, integration_id: int) -> None:
    """Update integration with Loki endpoint data.

    Args:
        harness: The harness to update the integration on.
        integration_id: The integration id.
    """

    harness.update_relation_data(
        integration_id,
        f"{TEST_REMOTE_APP}/0",
        {"endpoint": '{"url": "http://loki0:3100/loki/api/v1/push"}'},
    )


def _add_integration(harness: Harness, units: int) -> int:
    """Add integration and units to the harness.

    Args:
        harness: The harness to add the integration to.
        units: The number of units to add to the integration.

    Returns:
        The integration id.
    """
    int_id = harness.add_relation(cos.METRICS_LOGGING_INTEGRATION_NAME, TEST_REMOTE_APP)
    for i in range(units):
        harness.add_relation_unit(int_id, f"{TEST_REMOTE_APP}/{i}")
    return int_id


def test_push_api_endpoint_joined_starts_promtail(harness: Harness, promtail: MagicMock):
    """
    arrange: Setup harness and a mocked promtail.
    act: Add integration and update integration data twice.
    assert: Promtail has been started with any of the Loki endpoint found and the Promtail binary.
    """
    harness.begin()

    int_id = _add_integration(harness, units=0)

    for i in range(2):
        harness.add_relation_unit(int_id, f"loki/{i}")
        harness.update_relation_data(
            int_id,
            f"loki/{i}",
            {"endpoint": f'{{"url": "http://loki{i}:3100/loki/api/v1/push"}}'},
        )
    _update_integration_with_promtail_binary(harness, int_id)

    promtail.start.assert_called()
    for call in promtail.start.call_args_list:
        assert call in [
            (
                (
                    Config(
                        f"http://loki{i}:3100/loki/api/v1/push",
                        ProxyConfig(),
                        PromtailDownloadInfo(
                            url=TEST_PROMTAIL_BINARY_ZIP_INFO["url"],
                            zip_sha256=TEST_PROMTAIL_BINARY_ZIP_INFO["zipsha"],
                            bin_sha256=TEST_PROMTAIL_BINARY_ZIP_INFO["binsha"],
                        ),
                    ),
                ),
            )
            for i in range(2)
        ]


def test_push_api_endpoint_joined_does_not_start_promtail_if_no_endpoint_found(
    harness: Harness, promtail: MagicMock
):
    """
    arrange: Setup harness and a mocked promtail.
    act: Add integration without endpoint data.
    assert: Promtail has not been started.
    """
    harness.begin()

    int_id = _add_integration(harness, units=0)
    _update_integration_with_promtail_binary(harness, int_id)

    assert promtail.start.call_count == 0


def test_push_api_endpoint_joined_does_not_start_promtail_if_no_binary_found(
    harness: Harness, promtail: MagicMock
):
    """
    arrange: Setup harness and a mocked promtail.
    act:
        1. Add integration without promtail binary info.
        2. Add integration with promtail binary info but wrong architecture.
    assert: Promtail has not been started in both cases.
    """
    harness.begin()

    # 1. Add integration without promtail binary info.
    int_id = _add_integration(harness, units=1)
    _update_integration_data_with_endpoint(harness, int_id)

    assert promtail.start.call_count == 0

    # 2. Add integration with promtail binary info but wrong architecture.
    harness.update_relation_data(
        int_id,
        TEST_REMOTE_APP,
        {"promtail_binary_zip_url": json.dumps({"wrong_arch": TEST_PROMTAIL_BINARY_ZIP_INFO})},
    )

    assert promtail.start.call_count == 0


def test_push_api_endpoint_joined_creates_event_timer(harness: Harness):
    """
    arrange: Setup harness and mock event timer.
    act: Add integration and update integration data.
    assert: Event Timer for promtail_health is created.
    """
    et_mock = Mock(EventTimer, autospec=True)
    harness.begin()

    harness.charm.cos_observer._event_timer = et_mock

    int_id = _add_integration(harness, units=1)
    _update_integration_data_with_endpoint(harness, int_id)
    _update_integration_with_promtail_binary(harness, int_id)

    et_mock.ensure_event_timer.assert_called_once_with("promtail-health", 5)


def test_push_api_endpoint_joined_without_integration_data_does_not_create_event_timer(
    harness: Harness, event_timer: Mock
):
    """
    arrange: Setup harness and mock event timer.
    act: Add integration without integration data.
    assert: Event Timer for promtail_health is NOT created.
    """
    harness.begin()

    harness.charm.cos_observer._event_timer = event_timer

    _add_integration(harness, units=1)

    assert event_timer.ensure_event_timer.call_count == 0


def test_on_promtail_health(harness: Harness, promtail: MagicMock, caplog: LogCaptureFixture):
    """
    arrange: Setup harness and an unhealthy promtail.
    act: Trigger update_status event.
    assert: The Observer logs an error and restarts Promtail.
    """
    promtail.is_running.return_value = False

    harness.begin()

    harness.charm.on.promtail_health.emit()

    promtail.restart.assert_called_once()
    assert caplog.record_tuples == [("cos", logging.ERROR, "Promtail is not running, restarting")]


def test_push_api_endpoint_departed_integration_removed(harness: Harness, promtail: MagicMock):
    """
    arrange: Setup harness and a mocked promtail.
    act: Add integration and remove integration.
    assert: Promtail has been stopped.
    """
    harness.begin()

    int_id = _add_integration(harness, units=1)
    harness.remove_relation(int_id)

    promtail.stop.assert_called_once()


def test_push_api_endpoint_departed_endpoints_still_existing(
    harness: Harness, promtail: MagicMock
):
    """
    arrange: Setup harness and a mocked promtail.
    act: Add integration and two units. Remove one unit from integration.
    assert: Promtail has not been stopped and gets restarted with updated Loki endpoint.
    """
    harness.begin()

    int_id = _add_integration(harness, units=0)
    for i in range(2):
        harness.add_relation_unit(int_id, f"{TEST_REMOTE_APP}/{i}")
        harness.update_relation_data(
            int_id,
            f"{TEST_REMOTE_APP}/{i}",
            {"endpoint": f'{{"url": "http://loki{i}:3100/loki/api/v1/push"}}'},
        )
    _update_integration_with_promtail_binary(harness, int_id)

    # We clear the calls to the mock to make sure we only check the last start from this test.
    promtail.start.reset_mock()

    harness.remove_relation_unit(int_id, f"{TEST_REMOTE_APP}/0")

    assert promtail.stop.call_count == 0
    promtail.start.assert_called_once_with(
        Config(
            "http://loki1:3100/loki/api/v1/push",
            ProxyConfig(),
            PromtailDownloadInfo(
                url=TEST_PROMTAIL_BINARY_ZIP_INFO["url"],
                zip_sha256=TEST_PROMTAIL_BINARY_ZIP_INFO["zipsha"],
                bin_sha256=TEST_PROMTAIL_BINARY_ZIP_INFO["binsha"],
            ),
        )
    )


def test_push_api_endpoint_departed_disables_event_timer_if_no_endpoint_is_found(
    harness: Harness, event_timer: MagicMock
):
    """
    arrange: Setup harness and event_timer
    act: Add integration and remove integration.
    assert: Event Timer for promtail_health is disabled.
    """
    harness.begin()

    harness.charm.cos_observer._event_timer = event_timer

    int_id = _add_integration(harness, units=1)
    harness.remove_relation(int_id)

    event_timer.disable_event_timer.assert_called_once()


def test_loki_integration_data_gets_validated(harness: Harness):
    """
    arrange: Setup harness and a mocked promtail.
    act: Add corrupt integration data.
    assert: The harness throws expected ValidationErrors.
    """
    harness.begin()

    int_id = _add_integration(harness, units=1)

    # 1. Add corrupt endpoint without a proper URL.
    with pytest.raises(ValidationError) as e:
        harness.update_relation_data(
            int_id,
            f"{TEST_REMOTE_APP}/0",
            {"endpoint": '{"url": "no-url"}'},
        )
    assert str(e.value) == (
        "1 validation error for LokiEndpoint\n"
        "url\n"
        "  invalid or missing URL scheme (type=value_error.url.scheme)"
    )

    # Correct the data in order to be able to check the promtail binary info.
    _update_integration_data_with_endpoint(harness, int_id)

    # 2. Add corrupt promtail binary info.
    promtail_binary_info = {"amd64": {"url": "no-url", "zipsha": {}, "binsha": []}}
    with pytest.raises(ValidationError) as e:
        harness.update_relation_data(
            int_id, TEST_REMOTE_APP, {"promtail_binary_zip_url": json.dumps(promtail_binary_info)}
        )
    assert str(e.value) == (
        "3 validation errors for PromtailBinary\n"
        "url\n"
        "  invalid or missing URL scheme (type=value_error.url.scheme)\n"
        "zipsha\n"
        "  str type expected (type=type_error.str)\n"
        "binsha\n"
        "  str type expected (type=type_error.str)"
    )


def test_metrics_logging_available_true(harness: Harness):
    """
    arrange: Setup harness.
    act: Add integration with one unit.
    assert: metrics_logging_available returns True.
    """
    harness.begin()

    int_id = _add_integration(harness, units=1)
    _update_integration_data_with_endpoint(harness, int_id)

    assert harness.charm.cos_observer.metrics_logging_available()


def test_metrics_logging_available_false(harness: Harness):
    """
    arrange: Setup harness.
    act: Add integration without units.
    assert: metrics_logging_available returns False.
    """
    harness.begin()

    _add_integration(harness, units=0)

    assert not harness.charm.cos_observer.metrics_logging_available()
