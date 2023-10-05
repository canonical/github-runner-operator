#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

from unittest.mock import MagicMock

from charm_state import State


def test_metrics_logging_available_true():
    """
    arrange: Setup mocked charm to return an integration.
    act: Access is_metrics_logging_available property.
    assert: metrics_logging_available returns True.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = [MagicMock()]

    state = State.from_charm(charm)

    assert state.is_metrics_logging_available


def test_metrics_logging_available_false():
    """
    arrange: Setup mocked charm to return no integration.
    act: Access is_metrics_logging_available property.
    assert: metrics_logging_available returns False.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = []

    state = State.from_charm(charm)

    assert not state.is_metrics_logging_available
