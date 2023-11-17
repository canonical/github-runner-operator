#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.
import os
from unittest.mock import MagicMock, patch

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


def test_aproxy_proxy_missing():
    """
    arrange: Setup mocked charm to use aproxy without configured http proxy.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = []
    charm.config = {"use-aproxy": "true"}

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(charm)


def test_proxy_invalid_format():
    """
    arrange: Setup mocked charm and invalid juju proxy settings.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = []

    url_without_scheme = "proxy.example.com:8080"
    with patch.dict(os.environ, {"JUJU_CHARM_HTTP_PROXY": url_without_scheme}):
        with pytest.raises(CharmConfigInvalidError):
            State.from_charm(charm)
