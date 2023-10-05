#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.


#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

import pytest
from pydantic import ValidationError

from charm_state import LokiEndpoint, State


class FakeLokiPushApiConsumer:
    def __init__(self, endpoints: list[dict]):
        self._loki_endpoints = endpoints

    @property
    def loki_endpoints(self):
        return self._loki_endpoints


def test_loki_endpoint_returns_first_endpoint_found():
    """
    arrange: Setup LokiPushApiConsumer to return endpoints.
    act: Access loki_endpoint property.
    assert: First Loki endpoint is returned.
    """
    loki_consumer = FakeLokiPushApiConsumer([{"url": f"http://test.loki{i}"} for i in range(3)])
    state = State.from_charm(loki_consumer)

    assert state.loki_endpoint == LokiEndpoint(url="http://test.loki0")


def test_loki_endpoint_returns_none():
    """
    arrange: Setup LokiPushApiConsumer to return no endpoints.
    act: Access loki_endpoint property.
    assert: None is returned.
    """
    loki_consumer = FakeLokiPushApiConsumer([])

    state = State.from_charm(loki_consumer)

    assert state.loki_endpoint is None


def test_loki_endpoint_gets_validated():
    """
    arrange: Setup LokiPushApiConsumer to return corrupt data.
    act: Access loki_endpoint property.
    assert: Expected ValidationErrors are thrown.
    """
    loki_consumer = FakeLokiPushApiConsumer([{"url": "no-url"}])
    state = State.from_charm(loki_consumer)

    with pytest.raises(ValidationError) as e:
        state.loki_endpoint
    assert str(e.value) == (
        "1 validation error for LokiEndpoint\n"
        "url\n"
        "  invalid or missing URL scheme (type=value_error.url.scheme)"
    )


def test_metrics_logging_available_true():
    """
    arrange: Setup LokiPushApiConsumer to return an endpoint.
    act: Access is_metrics_logging_available property.
    assert: metrics_logging_available returns True.
    """
    loki_consumer = FakeLokiPushApiConsumer([{"url": "http://test.loki"}])

    state = State.from_charm(loki_consumer)

    assert state.is_metrics_logging_available


def test_metrics_logging_available_false():
    """
    arrange: Setup LokiPushApiConsumer to return no endpoint.
    act: Access is_metrics_logging_available property.
    assert: metrics_logging_available returns True.
    """
    loki_consumer = FakeLokiPushApiConsumer([])

    state = State.from_charm(loki_consumer)

    assert not state.is_metrics_logging_available
