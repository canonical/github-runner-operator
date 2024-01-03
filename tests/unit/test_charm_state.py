# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import os
import platform
from unittest.mock import MagicMock, patch

import pytest

from charm import GithubRunnerCharm
from charm_state import ARCH, CharmConfigInvalidError, State


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
    charm.config = {"experimental-use-aproxy": "true"}

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


def test_from_charm_invalid_arch(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a monkeypatched platform.machine that returns an unsupported architecture type.
    act: when _get_supported_arch is called.
    assert: a charm config invalid error is raised.
    """
    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = "i686"  # 32 bit is unsupported
    monkeypatch.setattr(platform, "machine", mock_machine)
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.config = {}

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(mock_charm)


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", ARCH.ARM64),
        pytest.param("arm64", ARCH.ARM64),
        pytest.param("x86_64", ARCH.X64),
    ],
)
def test_from_charm_arch(monkeypatch: pytest.MonkeyPatch, arch: str, expected_arch: ARCH):
    """
    arrange: Given a monkeypatched platform.machine that returns parametrized architectures.
    act: when _get_supported_arch is called.
    assert: a correct architecture is inferred.
    """
    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = arch
    monkeypatch.setattr(platform, "machine", mock_machine)
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.config = {}

    state = State.from_charm(mock_charm)

    assert state.arch == expected_arch
