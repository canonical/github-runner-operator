#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import pytest
from openstack.identity.v3 import project
from openstack.test import fakes

import openstack_manager
from errors import OpenStackUnauthorizedError

CLOUD_NAME = "microstack"


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack(monkeypatch: pytest.MonkeyPatch, projects) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    mock_connect.return_value.list_projects.return_value = projects
    monkeypatch.setattr("openstack_manager.openstack.connect", mock_connect)

    return mock_connect


@pytest.fixture(name="projects")
def projects_fixture() -> list:
    """Mocked list of projects."""
    return list(fakes.generate_fake_resources(project.Project, count=3))


def test_list_projects(clouds_yaml: dict, openstack_connect_mock: MagicMock, projects):
    """
    arrange: Mocked clouds.yaml data.
    act: Call initialize and list_projects.
    assert: openstack.connect and list_projects is called and the projects are returned.
    """
    actual_projects = openstack_manager.list_projects(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
    assert actual_projects == projects


def test_list_projects_openstack_uses_first_cloud(
    clouds_yaml: dict, openstack_connect_mock: MagicMock
):
    """
    arrange: Mocked clouds.yaml data with multiple clouds.
    act: Call initialize and list_projects.
    assert: openstack.connect is called with the first cloud name.
    """
    clouds_yaml["clouds"]["microstack2"] = clouds_yaml["clouds"][CLOUD_NAME]

    openstack_manager.list_projects(clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)


def test_list_projects_missing_credentials_error(
    clouds_yaml: dict, openstack_connect_mock: MagicMock
):
    """
    arrange: Mocked clouds.yaml data and openstack.list_projects raising keystone...Unauthorized.
    act: Call initialize and list_projects.
    assert: UnauthorizedError is raised.
    """
    openstack_connect_mock.return_value.list_projects.side_effect = (
        keystoneauth1.exceptions.http.Unauthorized
    )

    with pytest.raises(OpenStackUnauthorizedError) as exc:
        openstack_manager.list_projects(clouds_yaml)
    assert "Unauthorized to connect to OpenStack." in str(exc)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)
