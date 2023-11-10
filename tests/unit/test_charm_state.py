#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

from unittest.mock import MagicMock

import pytest

from charm_state import CharmConfigInvalidError, State


def test_metrics_logging_available_true():
    """
    arrange: Setup mocked charm to return an integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns True.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = [MagicMock()]
    charm.config = {}

    state = State.from_charm(charm)

    assert state.is_metrics_logging_available


def test_metrics_logging_available_false():
    """
    arrange: Setup mocked charm to return no integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns False.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = []
    charm.config = {}

    state = State.from_charm(charm)

    assert not state.is_metrics_logging_available


def test_invalid_aproxy_proxy():
    """
    arrange: Setup mocked charm to return an invalid proxy url.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = []
    charm.config = {"aproxy-proxy": "invalid"}

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(charm)
