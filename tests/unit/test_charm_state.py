# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import os
import platform
import secrets
from unittest.mock import MagicMock, patch

import ops
import pytest

import charm_state
from charm import GithubRunnerCharm
from charm_state import (
    ARCH,
    COS_AGENT_INTEGRATION_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    CharmConfigInvalidError,
    SSHDebugConnection,
    State,
)
from errors import OpenStackInvalidConfigError


@pytest.fixture(name="charm")
def charm() -> MagicMock:
    """Mock a charm instance with no relation data and minimal configuration.

    Returns:
        MagicMock: A mocked charm instance.
    """
    mock_charm = MagicMock(spec=GithubRunnerCharm)
    mock_charm.config = {"runner-storage": "juju-storage"}
    mock_charm.model.relations.__getitem__.return_value = []

    return mock_charm


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


def test_metrics_logging_available_true(charm: MagicMock):
    """
    arrange: Setup mocked charm to return an integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns True.
    """
    charm.model.relations = {
        COS_AGENT_INTEGRATION_NAME: MagicMock(spec=ops.Relation),
        DEBUG_SSH_INTEGRATION_NAME: None,
    }

    state = State.from_charm(charm)

    assert state.is_metrics_logging_available


def test_metrics_logging_available_false(charm: MagicMock):
    """
    arrange: Setup mocked charm to return no integration.
    act: Retrieve state from charm.
    assert: metrics_logging_available returns False.
    """

    state = State.from_charm(charm)

    assert not state.is_metrics_logging_available


def test_aproxy_proxy_missing(charm: MagicMock):
    """
    arrange: Setup mocked charm to use aproxy without configured http proxy.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm.config["experimental-use-aproxy"] = "true"

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(charm)
    assert "Invalid proxy configuration" in str(exc.value)


def test_proxy_invalid_format(charm: MagicMock):
    """
    arrange: Setup mocked charm and invalid juju proxy settings.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    url_without_scheme = "proxy.example.com:8080"
    with patch.dict(os.environ, {"JUJU_CHARM_HTTP_PROXY": url_without_scheme}):
        with pytest.raises(CharmConfigInvalidError):
            State.from_charm(charm)


def test_from_charm_invalid_arch(monkeypatch: pytest.MonkeyPatch, charm: MagicMock):
    """
    arrange: Given a monkeypatched platform.machine that returns an unsupported architecture type.
    act: when _get_supported_arch is called.
    assert: a charm config invalid error is raised.
    """
    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = "i686"  # 32 bit is unsupported
    monkeypatch.setattr(platform, "machine", mock_machine)

    with pytest.raises(CharmConfigInvalidError):
        State.from_charm(charm)


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", ARCH.ARM64),
        pytest.param("arm64", ARCH.ARM64),
        pytest.param("x86_64", ARCH.X64),
    ],
)
def test_from_charm_arch(
    monkeypatch: pytest.MonkeyPatch, arch: str, expected_arch: ARCH, charm: MagicMock
):
    """
    arrange: Given a monkeypatched platform.machine that returns parametrized architectures.
    act: when _get_supported_arch is called.
    assert: a correct architecture is inferred.
    """
    mock_machine = MagicMock(spec=platform.machine)
    mock_machine.return_value = arch
    monkeypatch.setattr(platform, "machine", mock_machine)

    state = State.from_charm(charm)

    assert state.arch == expected_arch


def test_ssh_debug_info_from_charm_no_relations(charm: MagicMock):
    """
    arrange: given a mocked charm that has no ssh-debug relations.
    act: when SSHDebug.from_charm is called.
    assert: None is returned.
    """
    charm.model.relations = {DEBUG_SSH_INTEGRATION_NAME: []}

    assert not SSHDebugConnection.from_charm(charm)


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
def test_from_charm_ssh_debug_info_error(invalid_relation_data: dict, charm: MagicMock):
    """
    arrange: Given an mocked charm that has invalid ssh-debug relation data.
    act: when from_charm is called.
    assert: CharmConfigInvalidError is raised.
    """
    mock_relation = MagicMock(spec=ops.Relation)
    mock_unit = MagicMock(spec=ops.Unit)
    mock_unit.name = "tmate-ssh-server-operator/0"
    mock_relation.units = {mock_unit}
    mock_relation.data = {mock_unit: invalid_relation_data}
    charm.model.relations = {DEBUG_SSH_INTEGRATION_NAME: [mock_relation]}
    charm.app.planned_units.return_value = 1
    charm.app.name = "github-runner-operator"
    charm.unit.name = "github-runner-operator/0"

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(charm)
    assert "Invalid SSH Debug info" in str(exc.value)


def test_from_charm_ssh_debug_info(charm: MagicMock):
    """
    arrange: Given an mocked charm that has invalid ssh-debug relation data.
    act: when from_charm is called.
    assert: ssh_debug_info data has been correctly parsed.
    """
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
    charm.model.relations = {
        DEBUG_SSH_INTEGRATION_NAME: [mock_relation],
        COS_AGENT_INTEGRATION_NAME: None,
    }
    charm.app.planned_units.return_value = 1
    charm.app.name = "github-runner-operator"
    charm.unit.name = "github-runner-operator/0"

    ssh_debug_connections = State.from_charm(charm).ssh_debug_connections
    assert str(ssh_debug_connections[0].host) == mock_relation_data["host"]
    assert str(ssh_debug_connections[0].port) == mock_relation_data["port"]
    assert ssh_debug_connections[0].rsa_fingerprint == mock_relation_data["rsa_fingerprint"]
    assert (
        ssh_debug_connections[0].ed25519_fingerprint == mock_relation_data["ed25519_fingerprint"]
    )


def test_invalid_runner_storage(charm: MagicMock):
    """
    arrange: Setup mocked charm with juju-storage as runner-storage.
    act: Change the runner-storage config to memory.
    assert: Configuration Error raised.
    """
    charm.config = {"runner-storage": "not-exist"}

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(charm)
    assert "Invalid runner-storage" in str(exc.value)


def test_openstack_config(charm: MagicMock, clouds_yaml: dict):
    """
    arrange: Setup mocked charm with openstack-clouds-yaml config.
    act: Retrieve state from charm.
    assert: openstack-clouds-yaml config is parsed correctly.
    """
    charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = json.dumps(clouds_yaml)
    state = State.from_charm(charm)
    assert state.charm_config.openstack_clouds_yaml == clouds_yaml


def test_openstack_config_invalid_yaml(charm: MagicMock):
    """
    arrange: Setup mocked charm with openstack-clouds-yaml config containing invalid yaml.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = "invalid_yaml\n-test: test\n"

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(charm)
    assert "Invalid openstack-clouds-yaml config. Invalid yaml." in str(exc.value)


def test_openstack_config_invalid_config(charm: MagicMock, clouds_yaml):
    """
    arrange: Setup mocked charm with openstack-clouds-yaml and openstack_manager
     to raise OpenStackInvalidConfigError.
    act: Retrieve state from charm.
    assert: CharmConfigInvalidError is raised.
    """
    charm.config[charm_state.OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = json.dumps(clouds_yaml)
    charm_state.openstack_manager.initialize.side_effect = OpenStackInvalidConfigError("invalid")

    with pytest.raises(CharmConfigInvalidError) as exc:
        State.from_charm(charm)
    assert "Invalid openstack config. Not able to initialize openstack integration." in str(
        exc.value
    )
