# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import os
import platform
from collections import defaultdict
from unittest.mock import MagicMock, patch

import ops
import pytest

from charm import GithubRunnerCharm
from charm_state import (
    ARCH,
    COS_AGENT_INTEGRATION_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    CharmConfigInvalidError,
    SSHDebugInfo,
    State,
)


def test_metrics_logging_available_true():
    """
    arrange: Setup mocked charm to return an integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns True.
    """
    charm = MagicMock()
    charm.model.relations = {
        COS_AGENT_INTEGRATION_NAME: MagicMock(spec=ops.Relation),
        DEBUG_SSH_INTEGRATION_NAME: None,
    }
    charm.config = {"runner-storage": "juju-storage"}

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
    charm.config = {"runner-storage": "juju-storage"}

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
    mock_charm.config = {"runner-storage": "juju-storage"}

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
    mock_charm.model.relations = defaultdict(lambda: None)
    mock_charm.config = {"runner-storage": "juju-storage"}

    state = State.from_charm(mock_charm)

    assert state.arch == expected_arch


def test_ssh_debug_info_from_charm_no_relations():
    """
    arrange: given a mocked charm that has no ssh-debug relations.
    act: when SSHDebug.from_charm is called.
    assert: None is returned.
    """
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.model.relations = {DEBUG_SSH_INTEGRATION_NAME: []}

    assert SSHDebugInfo.from_charm(mock_charm) is None


@pytest.mark.parametrize(
    "invalid_relation_data",
    [
        pytest.param(
            {
                "host": "invalidip",
                "port": "8080",
                "rsa_fingerprint": "SHA:fingerprint_data",
                "ed25519_fingerprint": "SHA:fingerprint_data",
            },
            id="invalid host IP",
        ),
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "invalidport",
                "rsa_fingerprint": "SHA:fingerprint_data",
                "ed25519_fingerprint": "SHA:fingerprint_data",
            },
            id="invalid port",
        ),
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "invalidport",
                "rsa_fingerprint": "invalid_fingerprint_data",
                "ed25519_fingerprint": "invalid_fingerprint_data",
            },
            id="invalid fingerprint",
        ),
    ],
)
def test_from_charm_ssh_debug_info_error(invalid_relation_data: dict):
    """
    arrange: Given an mocked charm that has invalid ssh-debug relation data.
    act: when from_charm is called.
    assert: CharmConfigInvalidError is raised.
    """
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.config = {}
    mock_relation = MagicMock(spec=ops.Relation)
    mock_unit = MagicMock(spec=ops.Unit)
    mock_unit.name = "tmate-ssh-server-operator/0"
    mock_relation.units = {mock_unit}
    mock_relation.data = {mock_unit: invalid_relation_data}
    mock_charm.model.relations = {DEBUG_SSH_INTEGRATION_NAME: [mock_relation]}
    mock_charm.app.planned_units.return_value = 1
    mock_charm.app.name = "github-runner-operator"
    mock_charm.unit.name = "github-runner-operator/0"

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(mock_charm)


def test_from_charm_ssh_debug_info():
    """
    arrange: Given an mocked charm that has invalid ssh-debug relation data.
    act: when from_charm is called.
    assert: ssh_debug_info data has been correctly parsed.
    """
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.config = {}
    mock_relation = MagicMock(spec=ops.Relation)
    mock_unit = MagicMock(spec=ops.Unit)
    mock_unit.name = "tmate-ssh-server-operator/0"
    mock_relation.units = {mock_unit}
    mock_relation.data = {
        mock_unit: (
            mock_relation_data := {
                "host": "127.0.0.1",
                "port": "8080",
                "rsa_fingerprint": "fingerprint_data",
                "ed25519_fingerprint": "fingerprint_data",
            }
        )
    }
    mock_charm.model.relations = {
        DEBUG_SSH_INTEGRATION_NAME: [mock_relation],
        COS_AGENT_INTEGRATION_NAME: None,
    }
    mock_charm.config = {"runner-storage": "juju-storage"}
    mock_charm.app.planned_units.return_value = 1
    mock_charm.app.name = "github-runner-operator"
    mock_charm.unit.name = "github-runner-operator/0"

    ssh_debug_info = State.from_charm(mock_charm).ssh_debug_info
    assert str(ssh_debug_info.host) == mock_relation_data["host"]
    assert str(ssh_debug_info.port) == mock_relation_data["port"]
    assert ssh_debug_info.rsa_fingerprint == mock_relation_data["rsa_fingerprint"]
    assert ssh_debug_info.ed25519_fingerprint == mock_relation_data["ed25519_fingerprint"]


def test_invalid_runner_storage():
    """
    arrange: Setup mocked charm with juju-storage as runner-storage.
    act: Change the runner-storage config to memory.
    assert: Configuration Error raised.
    """
    charm = MagicMock()
    charm.model.relations.__getitem__.return_value = [MagicMock()]
    charm.config = {"runner-storage": "not-exist"}

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(charm)
