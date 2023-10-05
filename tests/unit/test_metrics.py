#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from requests import HTTPError
from requests_mock import Mocker as RequestsMocker

from metrics import RunnerInstalled, issue_event

TEST_LOKI_PUSH_API_URL = "http://loki:3100/api/prom/push"


class FakeLokiServer:
    """Fake Loki server that stores logs."""

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


def test_issue_metrics_post_events_to_promtail(
    requests_mock: RequestsMocker, monkeypatch: MonkeyPatch
):
    """
    arrange: Mock promtail to be running and requests.post and Promtail server
    act: Issue a metric event
    assert: Fake Promtail issues expected log
    """
    t_mock = Mock()
    t_mock.time_ns.return_value = 12345
    monkeypatch.setattr("metrics.time", t_mock)
    loki_server = FakeLokiServer()

    def post_callback(request, context):
        context.status_code = 200
        loki_server.issue_log(request)
        return ""

    requests_mock.post(TEST_LOKI_PUSH_API_URL, text=post_callback)

    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    issue_event(event, TEST_LOKI_PUSH_API_URL)

    assert loki_server.logs == [
        (
            12345,
            {"event": "runner_installed", "timestamp": 123, "flavor": "small", "duration": 456},
        )
    ]


def test_issue_metrics_post_raises_on_error(requests_mock: RequestsMocker):
    """
    arrange: Mock requests.post to return 500
    act: Issue a metric event
    assert: issue_event raises an exception
    """

    requests_mock.post(TEST_LOKI_PUSH_API_URL, status_code=500)

    event = RunnerInstalled(timestamp=123, flavor="small", duration=456)

    with pytest.raises(HTTPError):
        issue_event(event, TEST_LOKI_PUSH_API_URL)
