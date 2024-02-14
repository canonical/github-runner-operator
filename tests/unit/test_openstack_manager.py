#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import pytest
import yaml

import openstack_manager

INVALID_CLOUDS_YAML_ERR_MSG = "Invalid clouds.yaml."

CLOUD_NAME = "microstack"


@pytest.fixture(autouse=True, name="clouds_yaml_path")
def clouds_yaml_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Mocked clouds.yaml path.

    Returns:
        Path: Mocked clouds.yaml path.
    """
    clouds_yaml_path = tmp_path / "clouds.yaml"
    monkeypatch.setattr("openstack_manager.CLOUDS_YAML_PATH", clouds_yaml_path)
    return clouds_yaml_path


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    monkeypatch.setattr("openstack_manager.openstack.connect", mock_connect)
    return mock_connect


def _create_clouds_yaml():
    """Create a fake clouds.yaml."""
    return {
        "clouds": {
            CLOUD_NAME: {
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


def test_initialize_openstack(clouds_yaml_path: Path, openstack_connect_mock: MagicMock):
    """
    arrange: Mocked clouds.yaml data and path.
    act: Call initialize_openstack.
    assert: openstack.connect is called with the correct cloud name and the clouds.yaml file
     is written to disk.
    """
    clouds_yaml = _create_clouds_yaml()

    openstack_manager.initialize_openstack(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
    assert yaml.safe_load(clouds_yaml_path.read_text(encoding="utf-8")) == clouds_yaml


def test_initialize_openstack_uses_first_cloud(
    clouds_yaml_path: Path, openstack_connect_mock: MagicMock
):
    """
    arrange: Mocked clouds.yaml data with multiple clouds.
    act: Call initialize_openstack.
    assert: openstack.connect is called with the first cloud name and the clouds.yaml file
     is written to disk.
    """
    clouds_yaml = _create_clouds_yaml()
    clouds_yaml["clouds"]["microstack2"] = clouds_yaml["clouds"][CLOUD_NAME]

    openstack_manager.initialize_openstack(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
    assert yaml.safe_load(clouds_yaml_path.read_text(encoding="utf-8")) == clouds_yaml


@pytest.mark.parametrize(
    "invalid_yaml, expected_err_msg",
    [
        pytest.param({"wrong-key": _create_clouds_yaml()["clouds"]}, INVALID_CLOUDS_YAML_ERR_MSG),
        pytest.param({}, INVALID_CLOUDS_YAML_ERR_MSG),
        pytest.param({"clouds": {}}, "No clouds defined in clouds.yaml."),
    ],
)
def test_initialize_openstack_validation_error(
    invalid_yaml: dict, expected_err_msg, openstack_connect_mock: MagicMock
):
    """
    arrange: Mocked clouds.yaml data with invalid data.
    act: Call initialize_openstack.
    assert: InvalidConfigError is raised and openstack.connect is not called.
    """

    with pytest.raises(openstack_manager.InvalidConfigError) as exc:
        openstack_manager.initialize_openstack(invalid_yaml)
    assert expected_err_msg in str(exc)

    openstack_connect_mock.assert_not_called()


def test_initialize_openstack_missing_credentials_error(openstack_connect_mock: MagicMock):
    """
    arrange: Mocked clouds.yaml data and openstack.connect raising MissingRequiredOptions.
    act: Call initialize_openstack.
    assert: InvalidConfigError is raised.
    """
    cloud_yaml = _create_clouds_yaml()
    openstack_connect_mock.side_effect = keystoneauth1.exceptions.MissingRequiredOptions(
        options=MagicMock()
    )
    with pytest.raises(openstack_manager.InvalidConfigError) as exc:
        openstack_manager.initialize_openstack(cloud_yaml)
    assert "Missing required Openstack credentials" in str(exc)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
