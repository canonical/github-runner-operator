#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
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


def test__create_connection(multi_clouds_yaml: dict, openstack_connect_mock: MagicMock):
    """
    arrange: given a cloud config yaml dict with multiple clouds.
    act: when _create_connection is called.
    assert: connection with first cloud in the config is used.
    """
    openstack_manager._create_connection(cloud_config=multi_clouds_yaml)

    openstack_connect_mock.assert_called_once_with(CLOUD_NAME)


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


def test__build_image_command():
    """
    arrange: given a mock Github runner application and proxy config.
    act: when _build_image_command is called.
    assert: command for build image bash script with args are returned.
    """
    test_runner_info = openstack_manager.RunnerApplication(
        os="linux",
        architecture="x64",
        download_url=(test_download_url := "https://testdownloadurl.com"),
        filename="test_filename",
        temp_download_token=secrets.token_hex(16),
    )
    test_proxy_config = openstack_manager.ProxyConfig(
        http=(test_http_proxy := "http://proxy.test"),
        https=(test_https_proxy := "https://proxy.test"),
        no_proxy=(test_no_proxy := "http://no.proxy"),
        use_aproxy=False,
    )

    command = openstack_manager._build_image_command(
        runner_info=test_runner_info, proxies=test_proxy_config
    )
    assert command == [
        "/usr/bin/bash",
        openstack_manager.BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME,
        test_download_url,
        test_http_proxy,
        test_https_proxy,
        test_no_proxy,
        f"""[Service]

Environment="HTTP_PROXY=http://proxy.test"


Environment="HTTPS_PROXY=https://proxy.test"


Environment="NO_PROXY=http://no.proxy"
""",
        '{"proxies": {"default": {"httpProxy": "http://proxy.test", "httpsProxy": '
        '"https://proxy.test", "noProxy": "http://no.proxy"}}}',
    ], "Unexpected build image command."


def test_build_image_runner_binary_error():
    """
    arrange: given a mocked github client get_runner_application function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.side_effect = openstack_manager.RunnerBinaryError

    with pytest.raises(openstack_manager.ImageBuildError) as exc:
        openstack_manager.build_image(
            arch=MagicMock(),
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
        )

    assert "Failed to fetch runner application." in str(exc)


def test_build_build_image_script_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched execute_command function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(side_effect=openstack_manager.SubprocessError),
    )

    with pytest.raises(openstack_manager.ImageBuildError) as exc:
        openstack_manager.build_image(
            arch=MagicMock(),
            cloud_config=MagicMock(),
            github_client=MagicMock(),
            path=MagicMock(),
        )

    assert "Failed to build image." in str(exc)


def test_build_image_delete_image_error(monkeypatch: pytest.MonkeyPatch, clouds_yaml: dict):
    """
    arrange: given a mocked openstack connection that returns existing images and delete_image
        that returns False (failed to delete image).
    act: when bulid_image is called.
    assert: ImageBuildError is raised.
    """
    mock_connection = MagicMock(spec=openstack_manager.openstack.connection.Connection)
    mock_connection.delete_image.return_value = False
    monkeypatch.setattr(
        openstack_manager,
        "_create_conection",
        MagicMock(spec=openstack_manager._create_connection, return_value=mock_connection),
    )

    with pytest.raises(openstack_manager.ImageBuildError) as exc:
        openstack_manager.build_image(
            arch=MagicMock(),
            cloud_config=MagicMock(),
            github_client=MagicMock(),
            path=MagicMock(),
            proxies=MagicMock(),
        )

    assert "Failed to delete duplicate image on Openstack." in str(exc)


def test_build_image_delete_image_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked connection that raises OpenStackCloudException on create_image.
    act: when bulid_image is called.
    assert: ImageBuildError is raised.
    """
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(spec=openstack_manager.execute_command),
    )
    mock_connection = MagicMock(spec=openstack_manager.openstack.connection.Connection)
    mock_connection.create_image.side_effect = openstack_manager.OpenStackCloudException
    monkeypatch.setattr(
        openstack_manager,
        "_create_connection",
        MagicMock(spec=openstack_manager._create_connection, return_value=mock_connection),
    )

    with pytest.raises(openstack_manager.ImageBuildError) as exc:
        openstack_manager.build_image(
            arch=MagicMock(),
            cloud_config=MagicMock(),
            github_client=MagicMock(),
            path=MagicMock(),
            proxies=None,
        )

    assert "Failed to upload image." in str(exc)


def test_build_image(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched execute_command and mocked openstack connection.
    act: when build_image is called.
    assert: Openstack image is successfully created.
    """
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(spec=openstack_manager.execute_command),
    )
    mock_connection = MagicMock(spec=openstack_manager.openstack.connection.Connection)
    monkeypatch.setattr(
        openstack_manager,
        "_create_connection",
        MagicMock(spec=openstack_manager._create_connection, return_value=mock_connection),
    )

    openstack_manager.build_image(
        arch=MagicMock(),
        cloud_config=MagicMock(),
        github_client=MagicMock(),
        path=MagicMock(),
    )
