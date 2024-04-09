#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from typing import Optional
from unittest.mock import MagicMock

import jinja2
import openstack.exceptions
import pytest

from charm_state import Arch, BaseImage
from errors import OpenStackUnauthorizedError
from openstack_cloud import openstack_manager

CLOUD_NAME = "microstack"


@pytest.fixture(autouse=True, name="openstack_connect_mock")
def mock_openstack_connect_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock openstack.connect."""
    mock_connect = MagicMock(spec=openstack_manager.openstack.connect)
    monkeypatch.setattr("openstack_cloud.openstack_manager.openstack.connect", mock_connect)

    return mock_connect


@pytest.fixture(name="mock_github_client")
def mock_github_client_fixture() -> MagicMock:
    """Mocked github client that returns runner application."""
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.return_value = openstack_manager.RunnerApplication(
        os="linux",
        architecture="x64",
        download_url="http://test_url",
        filename="test_filename",
        temp_download_token="test_token",
    )
    return mock_github_client


@pytest.fixture(name="patch_execute_command")
def patch_execute_command_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch execute command to a MagicMock instance."""
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(spec=openstack_manager.execute_command),
    )


@pytest.fixture(name="patched_create_connection_context")
def patched_create_connection_context_fixture(monkeypatch: pytest.MonkeyPatch):
    """Return a mocked openstack connection context manager and patch create_connection."""
    mock_connection = MagicMock(spec=openstack_manager.openstack.connection.Connection)
    monkeypatch.setattr(
        openstack_manager,
        "_create_connection",
        MagicMock(spec=openstack_manager._create_connection, return_value=mock_connection),
    )
    return mock_connection.__enter__()


@pytest.fixture(name="build_image_config")
def build_image_config_fixture():
    """Return a test build image config."""
    return openstack_manager.BuildImageConfig(
        arch=Arch.X64,
        base_image=BaseImage.NOBLE,
        proxies=openstack_manager.ProxyConfig(
            http="http://test.internal",
            https="https://test.internal",
            no_proxy="http://no_proxy.internal",
        ),
    )


def test__create_connection_error(clouds_yaml: dict, openstack_connect_mock: MagicMock):
    """
    arrange: given a monkeypatched connection.authorize() function that raises an error.
    act: when _create_connection is called.
    assert: OpenStackUnauthorizedError is raised.
    """
    connection_mock = MagicMock()
    connection_context = MagicMock()
    connection_context.authorize.side_effect = openstack.exceptions.HttpException
    connection_mock.__enter__.return_value = connection_context
    openstack_connect_mock.return_value = connection_mock

    with pytest.raises(OpenStackUnauthorizedError) as exc:
        with openstack_manager._create_connection(cloud_config=clouds_yaml):
            pass

    assert "Unauthorized credentials" in str(exc)


def test__create_connection(
    multi_clouds_yaml: dict, clouds_yaml: dict, cloud_name: str, openstack_connect_mock: MagicMock
):
    """
    arrange: given a cloud config yaml dict with 1. multiple clouds 2. single cloud.
    act: when _create_connection is called.
    assert: connection with first cloud in the config is used.
    """
    # 1. multiple clouds
    with openstack_manager._create_connection(cloud_config=multi_clouds_yaml):
        openstack_connect_mock.assert_called_with(cloud=CLOUD_NAME)

    # 2. single cloud
    with openstack_manager._create_connection(cloud_config=clouds_yaml):
        openstack_connect_mock.assert_called_with(cloud=cloud_name)


@pytest.mark.parametrize(
    "arch",
    [
        pytest.param("s390x", id="s390x"),
        pytest.param("riscv64", id="riscv64"),
        pytest.param("ppc64el", id="ppc64el"),
        pytest.param("armhf", id="armhf"),
        pytest.param("test", id="test"),
    ],
)
def test__get_supported_runner_arch_invalid_arch(arch: str):
    """
    arrange: given supported architectures.
    act: when _get_supported_runner_arch is called.
    assert: supported cloud image architecture type is returned.
    """
    with pytest.raises(openstack_manager.UnsupportedArchitectureError) as exc:
        openstack_manager._get_supported_runner_arch(arch=arch)

    assert arch in str(exc)


@pytest.mark.parametrize(
    "arch, image_arch",
    [
        pytest.param("x64", "amd64", id="x64"),
        pytest.param("arm64", "arm64", id="arm64"),
    ],
)
def test__get_supported_runner_arch(arch: str, image_arch: str):
    """
    arrange: given supported architectures.
    act: when _get_supported_runner_arch is called.
    assert: supported cloud image architecture type is returned.
    """
    assert openstack_manager._get_supported_runner_arch(arch=arch) == image_arch


@pytest.mark.parametrize(
    "proxy_config, dockerhub_mirror, ssh_debug_connections, expected_env_contents",
    [
        pytest.param(
            None,
            None,
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=
""",
            id="all values empty",
        ),
        pytest.param(
            openstack_manager.ProxyConfig(
                http="http://test.internal",
                https="https://test.internal",
                no_proxy="http://no_proxy.internal",
            ),
            None,
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

HTTP_PROXY=http://test.internal
http_proxy=http://test.internal


HTTPS_PROXY=https://test.internal
https_proxy=https://test.internal



NO_PROXY=http://no_proxy.internal
no_proxy=http://no_proxy.internal


LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=
""",
            id="proxy value set",
        ),
        pytest.param(
            None,
            "http://dockerhub_mirror.test",
            None,
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





DOCKERHUB_MIRROR=http://dockerhub_mirror.test
CONTAINER_REGISTRY_URL=http://dockerhub_mirror.test

LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=
""",
            id="dockerhub mirror set",
        ),
        pytest.param(
            None,
            None,
            [
                openstack_manager.SSHDebugConnection(
                    host="127.0.0.1",
                    port=10022,
                    rsa_fingerprint="SHA256:testrsa",
                    ed25519_fingerprint="SHA256:tested25519",
                )
            ],
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin





LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=

TMATE_SERVER_HOST=127.0.0.1
TMATE_SERVER_PORT=10022
TMATE_SERVER_RSA_FINGERPRINT=SHA256:testrsa
TMATE_SERVER_ED25519_FINGERPRINT=SHA256:tested25519
""",
            id="ssh debug connection set",
        ),
        pytest.param(
            openstack_manager.ProxyConfig(
                http="http://test.internal",
                https="https://test.internal",
                no_proxy="http://no_proxy.internal",
            ),
            "http://dockerhub_mirror.test",
            [
                openstack_manager.SSHDebugConnection(
                    host="127.0.0.1",
                    port=10022,
                    rsa_fingerprint="SHA256:testrsa",
                    ed25519_fingerprint="SHA256:tested25519",
                )
            ],
            """PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

HTTP_PROXY=http://test.internal
http_proxy=http://test.internal


HTTPS_PROXY=https://test.internal
https_proxy=https://test.internal



NO_PROXY=http://no_proxy.internal
no_proxy=http://no_proxy.internal


DOCKERHUB_MIRROR=http://dockerhub_mirror.test
CONTAINER_REGISTRY_URL=http://dockerhub_mirror.test

LANG=C.UTF-8
ACTIONS_RUNNER_HOOK_JOB_STARTED=

TMATE_SERVER_HOST=127.0.0.1
TMATE_SERVER_PORT=10022
TMATE_SERVER_RSA_FINGERPRINT=SHA256:testrsa
TMATE_SERVER_ED25519_FINGERPRINT=SHA256:tested25519
""",
            id="all values set",
        ),
    ],
)
def test__generate_runner_env(
    proxy_config: Optional[openstack_manager.ProxyConfig],
    dockerhub_mirror: Optional[str],
    ssh_debug_connections: Optional[list[openstack_manager.SSHDebugConnection]],
    expected_env_contents: str,
):
    """
    arrange: given configuration values for runner environment.
    act: when _generate_runner_env is called.
    assert: expected .env contents are generated.
    """
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)
    assert (
        openstack_manager._generate_runner_env(
            templates_env=environment,
            proxies=proxy_config,
            dockerhub_mirror=dockerhub_mirror,
            ssh_debug_connections=ssh_debug_connections,
        )
        == expected_env_contents
    )


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
    test_base_image = BaseImage.NOBLE

    command = openstack_manager._build_image_command(
        runner_info=test_runner_info,
        proxies=test_proxy_config,
        base_image=test_base_image,
    )
    assert command == [
        "/usr/bin/bash",
        openstack_manager.BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME,
        test_download_url,
        test_http_proxy,
        test_https_proxy,
        test_no_proxy,
        f"""[Service]

Environment="HTTP_PROXY={test_http_proxy}"


Environment="HTTPS_PROXY={test_https_proxy}"


Environment="NO_PROXY={test_no_proxy}"
""",
        f"""{{"proxies": {{"default": {{"httpProxy": "{test_http_proxy}", \
"httpsProxy": "{test_https_proxy}", "noProxy": "{test_no_proxy}"}}}}}}""",
        test_base_image.value,
    ], "Unexpected build image command."


def test_build_image_runner_binary_error(build_image_config: openstack_manager.BuildImageConfig):
    """
    arrange: given a mocked github client get_runner_application function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    mock_github_client = MagicMock(spec=openstack_manager.GithubClient)
    mock_github_client.get_runner_application.side_effect = openstack_manager.RunnerBinaryError

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
            config=build_image_config,
        )

    assert "Failed to fetch runner application." in str(exc)


def test_build_image_script_error(
    monkeypatch: pytest.MonkeyPatch, build_image_config: openstack_manager.BuildImageConfig
):
    """
    arrange: given a monkeypatched execute_command function that raises an error.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    monkeypatch.setattr(
        openstack_manager,
        "execute_command",
        MagicMock(
            side_effect=openstack_manager.SubprocessError(
                cmd=[], return_code=1, stdout="", stderr=""
            )
        ),
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            cloud_config=MagicMock(),
            github_client=MagicMock(),
            path=MagicMock(),
            config=build_image_config,
        )

    assert "Failed to build image." in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_runner_arch_error(
    monkeypatch: pytest.MonkeyPatch,
    mock_github_client: MagicMock,
    build_image_config: openstack_manager.BuildImageConfig,
):
    """
    arrange: given _get_supported_runner_arch that raises unsupported architecture error.
    act: when build_image is called.
    assert: ImageBuildError error is raised with unsupported arch message.
    """
    mock_get_supported_runner_arch = MagicMock(
        spec=openstack_manager._get_supported_runner_arch,
        side_effect=openstack_manager.UnsupportedArchitectureError(arch="x64"),
    )
    monkeypatch.setattr(
        openstack_manager, "_get_supported_runner_arch", mock_get_supported_runner_arch
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
            config=build_image_config,
        )

    assert "Unsupported architecture" in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_delete_image_error(
    mock_github_client: MagicMock,
    patched_create_connection_context: MagicMock,
    build_image_config: openstack_manager.BuildImageConfig,
):
    """
    arrange: given a mocked openstack connection that returns existing images and delete_image \
        that returns False (failed to delete image).
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    patched_create_connection_context.search_images.return_value = (
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
    )
    patched_create_connection_context.delete_image.return_value = False

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
            config=build_image_config,
        )

    assert "Failed to delete duplicate image on Openstack." in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image_create_image_error(
    patched_create_connection_context: MagicMock,
    mock_github_client: MagicMock,
    build_image_config: openstack_manager.BuildImageConfig,
):
    """
    arrange: given a mocked connection that raises OpenStackCloudException on create_image.
    act: when build_image is called.
    assert: ImageBuildError is raised.
    """
    patched_create_connection_context.create_image.side_effect = (
        openstack_manager.OpenStackCloudException
    )

    with pytest.raises(openstack_manager.OpenstackImageBuildError) as exc:
        openstack_manager.build_image(
            cloud_config=MagicMock(),
            github_client=mock_github_client,
            path=MagicMock(),
            config=build_image_config,
        )

    assert "Failed to upload image" in str(exc)


@pytest.mark.usefixtures("patch_execute_command")
def test_build_image(
    patched_create_connection_context: MagicMock,
    mock_github_client: MagicMock,
    build_image_config: openstack_manager.BuildImageConfig,
):
    """
    arrange: given monkeypatched execute_command and mocked openstack connection.
    act: when build_image is called.
    assert: Openstack image is successfully created.
    """
    patched_create_connection_context.search_images.return_value = (
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
        MagicMock(spec=openstack_manager.openstack.image.v2.image.Image),
    )

    openstack_manager.build_image(
        cloud_config=MagicMock(),
        github_client=mock_github_client,
        path=MagicMock(),
        config=build_image_config,
    )
