# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import os
import platform
import secrets
from typing import Any
from unittest.mock import MagicMock, patch

import ops
import pytest

import charm_state
from charm_state import (
    ARCH,
    COS_AGENT_INTEGRATION_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    CharmConfigInvalidError,
    SSHDebugConnection,
    State,
)
from tests.unit.factories import MockGithubRunnerCharmFactory


@pytest.fixture(name="clouds_yaml")
def clouds_yaml() -> dict:
    """Mocked clouds.yaml data.

    Returns:
        dict: Mocked clouds.yaml data.
    """
    return {
        "clouds": {
            "microstack": {
                "auth": {
                    "auth_url": secrets.token_hex(16),
                    "project_name": secrets.token_hex(16),
                    "project_domain_name": secrets.token_hex(16),
                    "username": secrets.token_hex(16),
                    "user_domain_name": secrets.token_hex(16),
                    "password": secrets.token_hex(16),
                }
            }
        }
    }


def test_metrics_logging_available_true():
    """
    arrange: Setup mocked charm to return an integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns True.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.model.relations = {
        COS_AGENT_INTEGRATION_NAME: MagicMock(spec=ops.Relation),
        DEBUG_SSH_INTEGRATION_NAME: [],
    }

    state = State.from_charm(mock_charm)

    assert state.is_metrics_logging_available


def test_metrics_logging_available_false():
    """
    arrange: Setup mocked charm to return no integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns False.
    """
    mock_charm = MockGithubRunnerCharmFactory()

    state = State.from_charm(mock_charm)

    assert not state.is_metrics_logging_available


def test_aproxy_proxy_missing():
    """
    arrange: Setup mocked charm to use aproxy without configured http proxy.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config["experimental-use-aproxy"] = "true"

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(mock_charm)
    assert "Invalid proxy configuration" in str(exc.value)


def test_proxy_invalid_format():
    """
    arrange: Setup mocked charm and invalid juju proxy settings.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()

    url_without_scheme = "proxy.example.com:8080"
    with patch.dict(os.environ, {"JUJU_CHARM_HTTP_PROXY": url_without_scheme}):
        with pytest.raises(CharmConfigInvalidError) as err:
            State.from_charm(mock_charm)
        assert "Invalid proxy configuration" in err.value.msg


def test_from_charm_invalid_arch(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a monkeypatched platform.machine that returns an unsupported architecture type.
    act: when _get_supported_arch is called.
    assert: a charm config invalid error is raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()

    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = "i686"  # 32 bit is unsupported
    monkeypatch.setattr(platform, "machine", mock_machine)

    with pytest.raises(CharmConfigInvalidError) as err:
        State.from_charm(mock_charm)
    assert "Unsupported architecture" in err.value.msg


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", ARCH.ARM64),
        pytest.param("arm64", ARCH.ARM64),
        pytest.param("x86_64", ARCH.X64),
    ],
)
def test_from_charm_arch(
    monkeypatch: pytest.MonkeyPatch,
    arch: str,
    expected_arch: ARCH,
):
    """
    arrange: Given a monkeypatched platform.machine that returns parametrized architectures.
    act: when _get_supported_arch is called.
    assert: a correct architecture is inferred.
    """
    mock_charm = MockGithubRunnerCharmFactory()

    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = arch
    monkeypatch.setattr(platform, "machine", mock_machine)

    state = State.from_charm(mock_charm)

    assert state.arch == expected_arch


def test_ssh_debug_info_from_charm_no_relations():
    """
    arrange: given a mocked charm that has no ssh-debug relations.
    act: when SSHDebug.from_charm is called.
    assert: None is returned.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.model.relations = {DEBUG_SSH_INTEGRATION_NAME: []}

    assert not SSHDebugConnection.from_charm(mock_charm)


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
    mock_charm = MockGithubRunnerCharmFactory()
    mock_relation = MagicMock(spec=ops.Relation)
    mock_unit = MagicMock(spec=ops.Unit)
    mock_unit.name = "tmate-ssh-server-operator/0"
    mock_relation.units = {mock_unit}
    mock_relation.data = {mock_unit: invalid_relation_data}
    mock_charm.model.relations[DEBUG_SSH_INTEGRATION_NAME] = [mock_relation]

    with pytest.raises(CharmConfigInvalidError) as err:
        State.from_charm(mock_charm)
    assert "Invalid SSH Debug info" in err.value.msg


def test_from_charm_ssh_debug_info():
    """
    arrange: Given an mocked charm that has invalid ssh-debug relation data.
    act: when from_charm is called.
    assert: ssh_debug_info data has been correctly parsed.
    """
    mock_charm = MockGithubRunnerCharmFactory()
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
    mock_charm.model.relations[DEBUG_SSH_INTEGRATION_NAME] = [mock_relation]

    ssh_debug_connections = State.from_charm(mock_charm).ssh_debug_connections
    assert str(ssh_debug_connections[0].host) == mock_relation_data["host"]
    assert str(ssh_debug_connections[0].port) == mock_relation_data["port"]
    assert ssh_debug_connections[0].rsa_fingerprint == mock_relation_data["rsa_fingerprint"]
    assert (
        ssh_debug_connections[0].ed25519_fingerprint == mock_relation_data["ed25519_fingerprint"]
    )


def test_invalid_runner_storage():
    """
    arrange: Setup mocked charm.
    act: Set runner-storage to a non-existing option.
    assert: Configuration Error raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config["runner-storage"] = "not-exist"

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(mock_charm)
    assert "Invalid runner-storage" in str(exc.value)


def test_openstack_config(clouds_yaml: dict):
    """
    arrange: Setup mocked charm with openstack-clouds-yaml config.
    act: Retrieve state from charm.
    assert: openstack-clouds-yaml config is parsed correctly.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = json.dumps(clouds_yaml)
    state = State.from_charm(mock_charm)
    assert state.charm_config.openstack_clouds_yaml == clouds_yaml


def test_openstack_config_invalid_yaml():
    """
    arrange: Setup mocked charm with openstack-clouds-yaml config containing invalid yaml.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = (
        "invalid_yaml\n-test: test\n"
    )

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(mock_charm)
    assert "Invalid openstack-clouds-yaml config. Invalid yaml." in str(exc.value)


@pytest.mark.parametrize(
    "clouds_yaml, expected_err_msg",
    [
        pytest.param(
            '["invalid", "type", "list"]',
            "Invalid openstack config format, expected dict, got <class 'list'>",
        ),
        pytest.param(
            "invalid string type",
            "Invalid openstack config format, expected dict, got <class 'str'>",
        ),
        pytest.param(
            "3",
            "Invalid openstack config format, expected dict, got <class 'int'>",
        ),
    ],
)
def test_openstack_config_invalid_format(clouds_yaml: Any, expected_err_msg: str):
    """
    arrange: Given a charm with openstack-clouds-yaml of types other than dict.
    act: when charm state is initialized.
    assert:
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = clouds_yaml
    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(mock_charm)
    assert expected_err_msg in str(exc)
