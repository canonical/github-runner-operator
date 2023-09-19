#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from requests import HTTPError
from requests_mock import Mocker as RequestsMocker

from metrics import PROMTAIL_PUSH_API_URL, RunnerInstalled, issue_event


class FakePromtailServer:
    """Fake Promtail server that stores issued logs."""

    def __init__(self):
        self.logs = []

    def issue_log(self, request):
        """Fake the issue of a log.

        Stores the log in the logs list.
        """
        data = request.json()
        ts = json.loads(data["streams"][0]["values"][0][0])
        event = json.loads(data["streams"][0]["values"][0][1])
        self.logs.append((ts, event))


@pytest.fixture(autouse=True, name="promtail_module")
def promtail_fixture(monkeypatch: MonkeyPatch) -> Mock:
    """Mock promtail."""
    promtail_mock = Mock()
    monkeypatch.setattr("metrics.promtail", promtail_mock)
    return promtail_mock


def test_issue_metrics_post_events_to_promtail(
    requests_mock: RequestsMocker, monkeypatch: MonkeyPatch, promtail_module: Mock
):
    """
    arrange: Mock promtail to be running and requests.post and Promtail server
    act: Issue a metric event
    assert: Fake Promtail issues expected log
    """
    t_mock = Mock()
    t_mock.time_ns.return_value = 12345
    promtail_module.is_running.return_value = True
    monkeypatch.setattr("metrics.time", t_mock)
    promtail_server = FakePromtailServer()

    def post_callback(request, context):
        context.status_code = 200
        promtail_server.issue_log(request)
        return ""

    requests_mock.post(PROMTAIL_PUSH_API_URL, text=post_callback)

    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    issue_event(event)

    assert promtail_server.logs == [
        (
            12345,
            {"event": "runner_installed", "timestamp": 123, "flavor": "small", "duration": 456},
        )
    ]


def test_issue_metrics_post_nothing_if_promtail_not_running(
    requests_mock: RequestsMocker, promtail_module: Mock
):
    """
    arrange: Mock promtail to be not running and requests.post
    act: Issue a metric event
    assert: Fake PromtailServer issues no log
    """
    promtail_module.is_running.return_value = False

    promtail_server = FakePromtailServer()

    def post_callback(request, context):
        context.status_code = 200
        promtail_server.issue_log(request)
        return ""

    requests_mock.post(PROMTAIL_PUSH_API_URL, text=post_callback)

    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    issue_event(event)

    assert not promtail_server.logs


def test_issue_metrics_post_raises_on_error(requests_mock: RequestsMocker, promtail_module: Mock):
    """
    arrange: Mock promtail to be running and requests.post to return 500
    act: Issue a metric event
    assert: issue_event raises an exception
    """
    promtail_module.is_running.return_value = True

    requests_mock.post(PROMTAIL_PUSH_API_URL, status_code=500)

    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    with pytest.raises(HTTPError):
        issue_event(event)
