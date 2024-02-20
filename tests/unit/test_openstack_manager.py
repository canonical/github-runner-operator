#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import pytest
import yaml
from openstack.identity.v3 import project
from openstack.test import fakes

import openstack_manager
from errors import OpenStackInvalidConfigError, OpenStackUnauthorizedError

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


@pytest.fixture(name="projects")
def projects_fixture() -> list:
    """Mocked list of projects."""
    return list(fakes.generate_fake_resources(project.Project, count=3))


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack(monkeypatch: pytest.MonkeyPatch, projects) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    mock_connect.return_value.list_projects.return_value = projects
    monkeypatch.setattr("openstack_manager.openstack.connect", mock_connect)

    return mock_connect


def _create_clouds_yaml() -> dict:
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


def test_initialize(clouds_yaml_path: Path):
    """
    arrange: Mocked clouds.yaml data and path.
    act: Call initialize.
    assert: The clouds.yaml file is written to disk.
    """
    clouds_yaml = _create_clouds_yaml()

    openstack_manager.initialize(clouds_yaml)

    assert yaml.safe_load(clouds_yaml_path.read_text(encoding="utf-8")) == clouds_yaml


@pytest.mark.parametrize(
    "invalid_yaml, expected_err_msg",
    [
        pytest.param({"wrong-key": _create_clouds_yaml()["clouds"]}, INVALID_CLOUDS_YAML_ERR_MSG),
        pytest.param({}, INVALID_CLOUDS_YAML_ERR_MSG),
        pytest.param({"clouds": {}}, "No clouds defined in clouds.yaml."),
        pytest.param(
            ["invalid", "type", "list"],
            "Invalid clouds.yaml format, expected dict, got <class 'list'>",
        ),
        pytest.param(
            {"invalid", "type", "set"},
            "Invalid clouds.yaml format, expected dict, got <class 'set'>",
        ),
        pytest.param(
            "invalid string type", "Invalid clouds.yaml format, expected dict, got <class 'str'>"
        ),
    ],
)
def test_initialize_validation_error(invalid_yaml: dict, expected_err_msg):
    """
    arrange: Mocked clouds.yaml data with invalid data.
    act: Call initialize.
    assert: InvalidConfigError is raised.
    """

    with pytest.raises(OpenStackInvalidConfigError) as exc:
        openstack_manager.initialize(invalid_yaml)
    assert expected_err_msg in str(exc)


def test_list_projects(clouds_yaml_path: Path, openstack_connect_mock: MagicMock, projects):
    """
    arrange: Mocked clouds.yaml data.
    act: Call initialize and list_projects.
    assert: openstack.connect and list_projects is called and the projects are returned.
    """
    clouds_yaml = _create_clouds_yaml()

    openstack_manager.initialize(clouds_yaml)
    actual_projects = openstack_manager.list_projects(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
    assert actual_projects == projects


def test_list_projects_openstack_uses_first_cloud(
    clouds_yaml_path: Path, openstack_connect_mock: MagicMock
):
    """
    arrange: Mocked clouds.yaml data with multiple clouds.
    act: Call initialize and list_projects.
    assert: openstack.connect is called with the first cloud name.
    """
    clouds_yaml = _create_clouds_yaml()
    clouds_yaml["clouds"]["microstack2"] = clouds_yaml["clouds"][CLOUD_NAME]

    openstack_manager.initialize(clouds_yaml)
    openstack_manager.list_projects(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)


def test_list_projects_missing_credentials_error(openstack_connect_mock: MagicMock):
    """
    arrange: Mocked clouds.yaml data and openstack.list_projects raising keystone...Unauthorized.
    act: Call initialize and list_projects.
    assert: UnauthorizedError is raised.
    """
    cloud_yaml = _create_clouds_yaml()
    openstack_connect_mock.return_value.list_projects.side_effect = (
        keystoneauth1.exceptions.http.Unauthorized
    )

    openstack_manager.initialize(cloud_yaml)

    with pytest.raises(OpenStackUnauthorizedError) as exc:
        openstack_manager.list_projects(cloud_yaml)
    assert "Unauthorized to connect to OpenStack." in str(exc)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
