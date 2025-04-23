# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import platform
import secrets
from unittest.mock import MagicMock

import pytest
import yaml
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from github_runner_manager.configuration.github import GitHubOrg, GitHubRepo
from pydantic import BaseModel
from pydantic.error_wrappers import ValidationError
from pydantic.networks import IPv4Address

import charm_state
from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    DOCKERHUB_MIRROR_CONFIG_NAME,
    FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME,
    GROUP_CONFIG_NAME,
    IMAGE_INTEGRATION_NAME,
    LABELS_CONFIG_NAME,
    MANAGER_SSH_PROXY_COMMAND_CONFIG_NAME,
    MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    RUNNER_HTTP_PROXY_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    USE_RUNNER_PROXY_FOR_TMATE_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    Arch,
    CharmConfig,
    CharmConfigInvalidError,
    CharmState,
    FlavorLabel,
    GithubConfig,
    OpenstackImage,
    OpenstackRunnerConfig,
    ProxyConfig,
    SSHDebugConnection,
    UnsupportedArchitectureError,
)
from errors import MissingMongoDBError
from tests.unit.factories import MockGithubRunnerCharmFactory


def test_github_config_from_charm_invalud_path():
    """
    arrange: Create an invalid GitHub path string and runner group name.
    act: Call parse_github_path with the invalid path string and runner group name.
    assert: Verify that the function raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[PATH_CONFIG_NAME] = "invalidpath/"
    mock_charm.config[GROUP_CONFIG_NAME] = "test_group"

    with pytest.raises(CharmConfigInvalidError):
        GithubConfig.from_charm(mock_charm)


def test_github_config_from_charm_empty_path():
    """
    arrange: Create a mock CharmBase instance with an empty path configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[PATH_CONFIG_NAME] = ""

    with pytest.raises(CharmConfigInvalidError):
        GithubConfig.from_charm(mock_charm)


def test_github_config_from_charm_invalid_token():
    """
    arrange: Create a mock CharmBase instance with an empty token configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[TOKEN_CONFIG_NAME] = ""

    with pytest.raises(CharmConfigInvalidError):
        GithubConfig.from_charm(mock_charm)


@pytest.mark.parametrize(
    "path_str, runner_group, expected_type, expected_attrs",
    [
        ("owner/repo", "test_group", GitHubRepo, {"owner": "owner", "repo": "repo"}),
        ("test_org", "test_group", GitHubOrg, {"org": "test_org", "group": "test_group"}),
    ],
)
def test_parse_github_path(
    path_str: str,
    runner_group: str,
    expected_type: GitHubRepo | GitHubOrg,
    expected_attrs: dict[str, str],
):
    """
    arrange: Create different GitHub path strings and runner group names.
    act: Call parse_github_path with the given path string and runner group name.
    assert: Verify that the function returns the expected type and attributes.
    """
    result = charm_state.parse_github_path(path_str, runner_group)

    # Assert
    assert isinstance(result, expected_type)
    for attr, value in expected_attrs.items():
        assert getattr(result, attr) == value


@pytest.mark.parametrize(
    "size, expected_result",
    [
        ("100KiB", True),
        ("10MiB", True),
        ("1GiB", True),
        ("0TiB", True),
        ("1000PiB", True),
        ("10000EiB", True),
        ("100KB", False),  # Invalid suffix
        ("100GB", False),  # Invalid suffix
        ("abc", False),  # Non-numeric characters
        ("100", False),  # No suffix
        ("100Ki", False),  # Incomplete suffix
        ("100.5MiB", False),  # Non-integer size
    ],
)
def test_valid_storage_size_str(size: str, expected_result: bool):
    """
    arrange: Provide storage size string.
    act: Call _valid_storage_size_str with the provided storage size string.
    assert: Verify that the function returns the expected result.
    """
    result = charm_state._valid_storage_size_str(size)

    assert result == expected_result


def test_parse_labels_invalid():
    """
    arrange: Provide labels string with an invalid label.
    act: Call _parse_labels with the provided labels string.
    assert: Verify that the function raises ValueError with the correct message.
    """
    labels = "label1, label 2, label3"  # Label containing space, should be considered invalid

    with pytest.raises(ValueError) as exc_info:
        charm_state._parse_labels(labels)
    assert str(exc_info.value) == "Invalid labels label 2 found."


@pytest.mark.parametrize(
    "labels, expected_valid_labels",
    [
        ("label1,label2,label3", ("label1", "label2", "label3")),  # All labels are valid
        ("label1, label2, label3", ("label1", "label2", "label3")),  # Labels with spaces
        ("label1,label2,label3,", ("label1", "label2", "label3")),  # Trailing comma
        ("label1,,label2,label3", ("label1", "label2", "label3")),  # Double commas
        ("label1,label2,label3, ", ("label1", "label2", "label3")),  # Trailing space
        ("", ()),  # Empty string
        (
            "label-1, label-2, label-3",
            ("label-1", "label-2", "label-3"),
        ),  # Labels with hyphens
    ],
)
def test_parse_labels(labels, expected_valid_labels):
    """
    arrange: Provide comma-separated labels string.
    act: Call _parse_labels with the provided labels string.
    assert: Verify that the function returns the expected valid labels.
    """
    result = charm_state._parse_labels(labels)

    assert result == expected_valid_labels


def test_parse_dockerhub_mirror_invalid_scheme():
    """
    arrange: Create a mock CharmBase instance with an invalid DockerHub mirror configuration.
    act: Call _parse_dockerhub_mirror method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[DOCKERHUB_MIRROR_CONFIG_NAME] = "http://example.com"

    with pytest.raises(CharmConfigInvalidError):
        CharmConfig._parse_dockerhub_mirror(mock_charm)


@pytest.mark.parametrize(
    "mirror_config, expected_mirror_url",
    [
        ("", None),
        ("https://example.com", "https://example.com"),
    ],
)
def test_parse_dockerhub_mirror(mirror_config: str, expected_mirror_url: str | None):
    """
    arrange: Create a mock CharmBase instance with provided DockerHub mirror configuration.
    act: Call _parse_dockerhub_mirror method with the mock CharmBase instance.
    assert: Verify that the method returns the expected DockerHub mirror URL or None.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[DOCKERHUB_MIRROR_CONFIG_NAME] = mirror_config

    result = CharmConfig._parse_dockerhub_mirror(mock_charm)

    assert result == expected_mirror_url


@pytest.fixture
def valid_yaml_config():
    """Valid YAML config."""
    return """
clouds:
    openstack:
        auth:
            username: 'admin'
            password: 'password'
            project_name: 'admin'
            auth_url: 'http://keystone.openstack.svc.cluster.local:5000/v3'
            user_domain_name: 'Default'
            project_domain_name: 'Default'
        region_name: 'RegionOne'
    """


@pytest.fixture
def invalid_yaml_config():
    """Invalid YAML config."""
    return """
clouds: asdfsadf
    openstack:
        auth:
            username: 'admin'
            password: 'password'
            project_name: 'admin'
            auth_url: 'http://keystone.openstack.svc.cluster.local:5000/v3'
            user_domain_name: 'Default'
            project_domain_name: 'Default'
        region_name: 'RegionOne'
    """


def test_parse_openstack_clouds_config_empty():
    """
    arrange: Create a mock CharmBase instance with an empty OpenStack clouds YAML config.
    act: Call _parse_openstack_clouds_config method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = ""

    with pytest.raises(CharmConfigInvalidError):
        CharmConfig._parse_openstack_clouds_config(mock_charm)


def test_parse_openstack_clouds_config_invalid_yaml(invalid_yaml_config: str):
    """
    arrange: Create a mock CharmBase instance with an invalid YAML config.
    act: Call _parse_openstack_clouds_config method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = invalid_yaml_config

    with pytest.raises(CharmConfigInvalidError):
        CharmConfig._parse_openstack_clouds_config(mock_charm)


def test_parse_openstack_clouds_config_invalid_yaml_list():
    """
    arrange: Create a mock CharmBase instance with an invalid YAML config.
    act: Call _parse_openstack_clouds_config method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = "-1\n-2\n-3"

    with pytest.raises(CharmConfigInvalidError):
        CharmConfig._parse_openstack_clouds_config(mock_charm)


def test_parse_openstack_clouds_config_valid(valid_yaml_config: str):
    """
    arrange: Create a mock CharmBase instance with a valid OpenStack clouds YAML config.
    act: Call _parse_openstack_clouds_config method with the mock CharmBase instance.
    assert: Verify that the method returns the parsed YAML dictionary.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = valid_yaml_config

    result = CharmConfig._parse_openstack_clouds_config(mock_charm)

    assert isinstance(result, dict)
    assert "clouds" in result


@pytest.mark.parametrize("reconcile_interval", [(0), (1)])
def test_check_reconcile_interval_invalid(reconcile_interval: int):
    """
    arrange: Provide an invalid reconcile interval value.
    act: Call check_reconcile_interval method with the provided value.
    assert: Verify that the method raises ValueError with the correct message.
    """
    with pytest.raises(ValueError) as exc_info:
        CharmConfig.check_reconcile_interval(reconcile_interval)
    assert (
        str(exc_info.value)
        == "The reconcile-interval configuration needs to be greater or equal to 2"
    )


@pytest.mark.parametrize("reconcile_interval", [(2), (5), (10)])
def test_check_reconcile_interval_valid(reconcile_interval: int):
    """
    arrange: Provide a valid reconcile interval value.
    act: Call check_reconcile_interval method with the provided value.
    assert: Verify that the method returns the same value.
    """
    result = CharmConfig.check_reconcile_interval(reconcile_interval)

    assert result == reconcile_interval


def test_charm_config_from_charm_invalid_github_config():
    """
    arrange: Create a mock CharmBase instance with an invalid GitHub configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[PATH_CONFIG_NAME] = ""

    # Act and Assert
    with pytest.raises(CharmConfigInvalidError) as exc_info:
        CharmConfig.from_charm(mock_charm)
    assert str(exc_info.value) == "Invalid Github config, Missing path configuration"


def test_charm_config_from_charm_invalid_reconcile_interval():
    """
    arrange: Create a mock CharmBase instance with an invalid reconcile interval.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[RECONCILE_INTERVAL_CONFIG_NAME] = ""

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        CharmConfig.from_charm(mock_charm)
    assert str(exc_info.value) == "The reconcile-interval config must be int"


def test_charm_config_from_charm_invalid_labels():
    """
    arrange: Create a mock CharmBase instance with an invalid reconcile interval.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[LABELS_CONFIG_NAME] = "hell world, space rangers"

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        CharmConfig.from_charm(mock_charm)
    assert "Invalid labels config" in str(exc_info.value)


def test_charm_config_from_charm_valid():
    """
    arrange: Create a mock CharmBase instance with valid configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method returns a CharmConfig instance with the expected values.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config = {
        PATH_CONFIG_NAME: "owner/repo",
        RECONCILE_INTERVAL_CONFIG_NAME: "5",
        DOCKERHUB_MIRROR_CONFIG_NAME: "https://example.com",
        # "clouds: { openstack: { auth: { username: 'admin' }}}"
        OPENSTACK_CLOUDS_YAML_CONFIG_NAME: yaml.safe_dump(
            (
                test_openstack_config := {
                    "clouds": {
                        "openstack": {
                            "auth": {
                                "auth_url": "https://project-keystone.url/",
                                "password": secrets.token_hex(16),
                                "project_domain_name": "Default",
                                "project_name": "test-project-name",
                                "user_domain_name": "Default",
                                "username": "test-user-name",
                            },
                            "region_name": secrets.token_hex(16),
                        }
                    }
                }
            )
        ),
        LABELS_CONFIG_NAME: "label1,label2,label3",
        TOKEN_CONFIG_NAME: "abc123",
        MANAGER_SSH_PROXY_COMMAND_CONFIG_NAME: "bash -c 'openssl s_client -quiet -connect example.com:2222 -servername %h 2>/dev/null'",
    }

    result = CharmConfig.from_charm(mock_charm)

    assert result.path == GitHubRepo(owner="owner", repo="repo")
    assert result.reconcile_interval == 5
    assert result.dockerhub_mirror == "https://example.com"
    assert result.openstack_clouds_yaml == test_openstack_config
    assert result.labels == ("label1", "label2", "label3")
    assert result.token == "abc123"
    assert "openssl s_client" in result.manager_proxy_command


def test_openstack_image_from_charm_no_connections():
    """
    arrange: Mock CharmBase instance without relation.
    act: Call OpenstackImage.from_charm method.
    assert: Verify that the method returns the expected None value.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    relation_mock.units = []
    mock_charm.model.relations[IMAGE_INTEGRATION_NAME] = []

    image = OpenstackImage.from_charm(mock_charm)

    assert image is None


def test_openstack_image_from_charm_data_not_ready():
    """
    arrange: Mock CharmBase instance with no relation data.
    act: Call OpenstackImage.from_charm method.
    assert: Verify that the method returns the expected None value for id and tags.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    unit_mock = MagicMock()
    relation_mock.units = [unit_mock]
    relation_mock.data = {unit_mock: {}}
    mock_charm.model.relations[IMAGE_INTEGRATION_NAME] = [relation_mock]

    image = OpenstackImage.from_charm(mock_charm)

    assert isinstance(image, OpenstackImage)
    assert image.id is None
    assert image.tags is None


def test_openstack_image_from_charm():
    """
    arrange: Mock CharmBase instance with relation data.
    act: Call OpenstackImage.from_charm method.
    assert: Verify that the method returns the expected image id and tags.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    unit_mock = MagicMock()
    relation_mock.units = [unit_mock]
    relation_mock.data = {
        unit_mock: {
            "id": (test_id := "test-id"),
            "tags": ",".join(test_tags := ["tag1", "tag2"]),
        }
    }
    mock_charm.model.relations[IMAGE_INTEGRATION_NAME] = [relation_mock]

    image = OpenstackImage.from_charm(mock_charm)

    assert isinstance(image, OpenstackImage)
    assert image.id == test_id
    assert image.tags == test_tags


@pytest.mark.parametrize(
    "http, https, expected_result",
    [
        ("http://proxy.example.com", None, True),  # Test with only http set
        (None, "https://secureproxy.example.com", True),  # Test with only https set
        (
            "http://proxy.example.com",
            "https://secureproxy.example.com",
            True,
        ),  # Test with both http and https set
        (None, None, False),  # Test with neither http nor https set
    ],
)
def test___bool__(http: str | None, https: str | None, expected_result: bool):
    """
    arrange: Create a YourClass instance with http and/or https set.
    act: Call the __bool__ method on the instance.
    assert: Verify that the method returns the expected boolean value.
    """
    proxy_instance = ProxyConfig(http=http, https=https)

    result = bool(proxy_instance)

    assert result == expected_result


@pytest.mark.parametrize(
    "http, https, no_proxy",
    [
        pytest.param(None, None, "localhost"),
        pytest.param(None, "http://internal.proxy", None),
    ],
)
def test_proxy_config_from_charm(
    monkeypatch: pytest.MonkeyPatch, http: str | None, https: str | None, no_proxy: str | None
):
    """
    arrange: Create a mock CharmBase instance with use-aproxy configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method returns a ProxyConfig instance with no_proxy set correctly.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[USE_APROXY_CONFIG_NAME] = False
    monkeypatch.setattr(charm_state, "get_env_var", MagicMock(side_effect=[http, https, no_proxy]))

    result = charm_state._build_proxy_config_from_charm()

    assert result.no_proxy is None


@pytest.mark.parametrize(
    "mocked_arch",
    [
        "ppc64le",  # Test with unsupported architecture
        "sparc",  # Another example of unsupported architecture
    ],
)
def test__get_supported_arch_unsupported(mocked_arch: str, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock the platform.machine() function to return an unsupported architecture.
    act: Call the _get_supported_arch function.
    assert: Verify that the function raises an UnsupportedArchitectureError.
    """
    monkeypatch.setattr(platform, "machine", MagicMock(return_value=mocked_arch))

    with pytest.raises(UnsupportedArchitectureError):
        charm_state._get_supported_arch()


@pytest.mark.parametrize(
    "mocked_arch, expected_result",
    [
        ("arm64", Arch.ARM64),  # Test with supported ARM64 architecture
        ("x86_64", Arch.X64),  # Test with supported X64 architecture
    ],
)
def test__get_supported_arch_supported(
    mocked_arch: str, expected_result: Arch, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock the platform.machine() function to return a specific architecture.
    act: Call the _get_supported_arch function.
    assert: Verify that the function returns the expected supported architecture.
    """
    monkeypatch.setattr(platform, "machine", MagicMock(return_value=mocked_arch))

    assert charm_state._get_supported_arch() == expected_result


def test_ssh_debug_connection_from_charm_no_connections():
    """
    arrange: Mock CharmBase instance without relation.
    act: Call SSHDebugConnection.from_charm method.
    assert: Verify that the method returns the expected empty list.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.model.relations[DEBUG_SSH_INTEGRATION_NAME] = []

    connections = charm_state._build_ssh_debug_connection_from_charm(mock_charm)

    assert not connections


def test_ssh_debug_connection_from_charm_data_not_ready():
    """
    arrange: Mock CharmBase instance with no relation data.
    act: Call SSHDebugConnection.from_charm method.
    assert: Verify that the method returns the expected list of SSHDebugConnection instances.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    unit_mock = MagicMock()
    relation_mock.units = [unit_mock]
    relation_mock.data = {unit_mock: {}}
    mock_charm.model.relations[DEBUG_SSH_INTEGRATION_NAME] = [relation_mock]

    connections = charm_state._build_ssh_debug_connection_from_charm(mock_charm)

    assert not connections


@pytest.mark.parametrize("use_runner_http_proxy", [True, False])
def test_ssh_debug_connection_from_charm(use_runner_http_proxy: bool):
    """
    arrange: Mock CharmBase instance with relation data.
    act: Call SSHDebugConnection.from_charm method.
    assert: Verify that the method returns the expected list of SSHDebugConnection instances.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[USE_RUNNER_PROXY_FOR_TMATE_CONFIG_NAME] = use_runner_http_proxy
    relation_mock = MagicMock()
    unit_mock = MagicMock()
    relation_mock.units = [unit_mock]
    relation_mock.data = {
        unit_mock: {
            "host": "192.168.0.1",
            "port": 22,
            "rsa_fingerprint": "SHA256:abcdef",
            "ed25519_fingerprint": "SHA256:ghijkl",
        }
    }
    mock_charm.model.relations[DEBUG_SSH_INTEGRATION_NAME] = [relation_mock]

    connections = charm_state._build_ssh_debug_connection_from_charm(mock_charm)

    assert isinstance(connections[0], SSHDebugConnection)
    assert connections[0].host == IPv4Address("192.168.0.1")
    assert connections[0].port == 22
    assert connections[0].rsa_fingerprint == "SHA256:abcdef"
    assert connections[0].ed25519_fingerprint == "SHA256:ghijkl"
    assert connections[0].use_runner_http_proxy == use_runner_http_proxy


def test_reactive_config_from_charm():
    """
    arrange: Mock CharmBase instance with relation data and config option set.
    act: Call ReactiveConfig.from_charm method.
    assert: Verify that the method returns the expected object.
    """
    mongodb_uri = "mongodb://user:password@localhost:27017"
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    app_mock = MagicMock()
    relation_mock.app = app_mock
    relation_mock.data = {
        app_mock: {
            "uris": mongodb_uri,
        }
    }
    mock_charm.model.relations[charm_state.MONGO_DB_INTEGRATION_NAME] = [relation_mock]
    database = DatabaseRequires(
        mock_charm, relation_name=charm_state.MONGO_DB_INTEGRATION_NAME, database_name="test"
    )

    connection_info = charm_state.ReactiveConfig.from_database(database)

    assert isinstance(connection_info, charm_state.ReactiveConfig)
    assert connection_info.mq_uri == mongodb_uri


def test_reactive_config_from_database_returns_none():
    """
    arrange: Mock CharmBase instance without relation data.
    act: Call ReactiveConfig.from_database method.
    assert: None is returned.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    app_mock = MagicMock()
    relation_mock.app = app_mock
    relation_mock.data = {}
    mock_charm.model.relations[charm_state.MONGO_DB_INTEGRATION_NAME] = []

    database = DatabaseRequires(
        mock_charm, relation_name=charm_state.MONGO_DB_INTEGRATION_NAME, database_name="test"
    )

    connection_info = charm_state.ReactiveConfig.from_database(database)

    assert connection_info is None


def test_reactive_config_from_database_integration_data_missing():
    """
    arrange: Mock CharmBase instance with relation but without data and with config option set.
    act: Call ReactiveConfig.from_charm method.
    assert: IntegrationDataMissingError is raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    relation_mock = MagicMock()
    app_mock = MagicMock()
    relation_mock.app = app_mock
    relation_mock.data = {}
    mock_charm.model.relations[charm_state.MONGO_DB_INTEGRATION_NAME] = [relation_mock]

    database = DatabaseRequires(
        mock_charm, relation_name=charm_state.MONGO_DB_INTEGRATION_NAME, database_name="test"
    )

    with pytest.raises(MissingMongoDBError) as exc:
        charm_state.ReactiveConfig.from_database(database)

    assert f"Missing uris for {charm_state.MONGO_DB_INTEGRATION_NAME} integration" in str(
        exc.value
    )


@pytest.fixture
def mock_charm_state_path():
    """Fixture to mock CHARM_STATE_PATH."""
    return MagicMock()


@pytest.fixture
def mock_charm_state_data():
    """Fixture to mock previous charm state data."""
    return {
        "arch": "x86_64",
        "is_metrics_logging_available": True,
        "proxy_config": {"http": "http://example.com", "https": "https://example.com"},
        "charm_config": {"token": secrets.token_hex(16)},
        "reactive_config": {"uri": "mongodb://user:password@localhost:27017"},
        "runner_config": {
            "virtual_machines": 2,
        },
        "ssh_debug_connections": [
            {"host": "10.1.2.4", "port": 22},
        ],
    }


class MockModel(BaseModel):
    """A Mock model class used for pydantic error testing."""


@pytest.mark.parametrize(
    "module, target, exc",
    [
        (charm_state, "_build_proxy_config_from_charm", ValidationError([], MockModel)),
        (charm_state, "_build_proxy_config_from_charm", ValueError),
        (CharmConfig, "from_charm", ValidationError([], MockModel)),
        (CharmConfig, "from_charm", ValueError),
        (charm_state, "_get_supported_arch", UnsupportedArchitectureError(arch="testarch")),
        (charm_state, "_build_ssh_debug_connection_from_charm", ValidationError([], MockModel)),
    ],
)
def test_charm_state_from_charm_invalid_cases(
    module: object, target: str, exc: Exception, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock CharmBase and necessary methods to raise the specified exceptions.
    act: Call CharmState.from_charm.
    assert: Ensure CharmConfigInvalidError is raised with the appropriate message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_database = MagicMock(spec=DatabaseRequires)
    monkeypatch.setattr("charm_state._build_proxy_config_from_charm", MagicMock())
    mock_charm_config = MagicMock()
    mock_charm_config.openstack_clouds_yaml = None
    mock_charm_config_from_charm = MagicMock()
    mock_charm_config_from_charm.return_value = mock_charm_config
    monkeypatch.setattr(CharmConfig, "from_charm", mock_charm_config_from_charm)
    monkeypatch.setattr(OpenstackRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "_get_supported_arch", MagicMock())
    monkeypatch.setattr(charm_state, "_build_ssh_debug_connection_from_charm", MagicMock())
    monkeypatch.setattr(module, target, MagicMock(side_effect=exc))

    with pytest.raises(CharmConfigInvalidError):
        CharmState.from_charm(mock_charm, mock_database)


def test_charm_state_from_charm(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm.
    assert: Ensure no errors are raised.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_database = MagicMock(spec=DatabaseRequires)
    monkeypatch.setattr("charm_state._build_proxy_config_from_charm", MagicMock())
    monkeypatch.setattr(CharmConfig, "from_charm", MagicMock())
    monkeypatch.setattr(OpenstackRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "_get_supported_arch", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr("charm_state._build_ssh_debug_connection_from_charm", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())

    assert CharmState.from_charm(mock_charm, mock_database)


@pytest.mark.parametrize(
    "virtual_machines,base_virtual_machines,max_total_virtual_machines,expected_base,expected_max",
    [
        (0, 0, 0, 0, 0),
        (3, 0, 0, 3, 3),
        (0, 1, 2, 1, 2),
        (0, 0, 2, 0, 2),
        (0, 2, 0, 2, 0),
    ],
)
def test_parse_virtual_machine_numbers(
    monkeypatch,
    virtual_machines,
    base_virtual_machines,
    max_total_virtual_machines,
    expected_base,
    expected_max,
):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm with the specified config options for number of machines.
    assert: There is a preference for base_virtual_machines and max_total_virtual_machines,
        but it both those config options are not set, then virtual_machines is used.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())
    mock_database = MagicMock(spec=DatabaseRequires)

    mock_charm.config[VIRTUAL_MACHINES_CONFIG_NAME] = virtual_machines
    mock_charm.config[BASE_VIRTUAL_MACHINES_CONFIG_NAME] = base_virtual_machines
    mock_charm.config[MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME] = max_total_virtual_machines
    state = CharmState.from_charm(mock_charm, mock_database)

    assert state.runner_config.base_virtual_machines == expected_base
    assert state.runner_config.max_total_virtual_machines == expected_max


@pytest.mark.parametrize(
    "virtual_machines,base_virtual_machines,max_total_virtual_machines,expected_error_message",
    [
        (
            1,
            2,
            3,
            "deprecated and new configuration are set for the number of machines to spawn",
        ),
        (
            3,
            1,
            0,
            "deprecated and new configuration are set for the number of machines to spawn",
        ),
        (
            3,
            0,
            1,
            "deprecated and new configuration are set for the number of machines to spawn",
        ),
    ],
)
def test_error_parse_virtual_machine_numbers(
    monkeypatch,
    virtual_machines,
    base_virtual_machines,
    max_total_virtual_machines,
    expected_error_message,
):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm with the specified config options for number of machines.
    assert: The exception CharmConfigInvalidError should be raised with the expected message
    """
    mock_charm = MockGithubRunnerCharmFactory()
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())
    mock_database = MagicMock(spec=DatabaseRequires)

    mock_charm.config[VIRTUAL_MACHINES_CONFIG_NAME] = virtual_machines
    mock_charm.config[BASE_VIRTUAL_MACHINES_CONFIG_NAME] = base_virtual_machines
    mock_charm.config[MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME] = max_total_virtual_machines
    with pytest.raises(CharmConfigInvalidError) as exc_info:
        _ = CharmState.from_charm(mock_charm, mock_database)
    assert expected_error_message in str(exc_info.value)


@pytest.mark.parametrize(
    "openstack_flavor,flavor_label_combinations,labels,expected_flavor_label_combinations,expected_labels",
    [
        ("m1.small", "", "", [FlavorLabel(flavor="m1.small", label=None)], ()),
        ("m1.small", "", "one,two", [FlavorLabel(flavor="m1.small", label=None)], ("one", "two")),
        (
            "",
            "m1.small:small",
            "one,two",
            [FlavorLabel(flavor="m1.small", label="small")],
            ("small", "one", "two"),
        ),
        (
            "m1.notused",
            "m1.small:small",
            "one,two",
            [FlavorLabel(flavor="m1.small", label="small")],
            ("small", "one", "two"),
        ),
    ],
)
def test_parse_flavor_config(
    monkeypatch,
    openstack_flavor,
    flavor_label_combinations,
    labels,
    expected_flavor_label_combinations,
    expected_labels,
):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm with the specified config options for the number of
       flavors and labels.
    assert: The correct flavors and labels should be generated.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())
    mock_charm.config[OPENSTACK_FLAVOR_CONFIG_NAME] = openstack_flavor
    mock_charm.config[FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME] = flavor_label_combinations
    mock_charm.config[LABELS_CONFIG_NAME] = labels

    mock_database = MagicMock(spec=DatabaseRequires)
    state = CharmState.from_charm(mock_charm, mock_database)
    assert state.charm_config.labels == expected_labels
    assert state.runner_config.flavor_label_combinations == expected_flavor_label_combinations


@pytest.mark.parametrize(
    "openstack_flavor,flavor_label_combinations,labels,expected_error_message",
    [
        ("", "", "", "flavor not specified"),
        ("", ",", "", "Invalid flavor-label"),
        ("", ",,", "", "Invalid flavor-label"),
        ("", "a:a,", "", "Invalid flavor-label"),
        ("", "a::a,", "", "Invalid flavor-label"),
        ("", ",a:a", "", "Invalid flavor-label"),
        ("", "a:a,,b:b", "", "Invalid flavor-label"),
        ("", "a", "", "Invalid flavor-label"),
        ("", ":zz", "", "empty flavor"),
        ("", "zz:", "", "empty label"),
        ("", "xx:yy,:", "", "empty flavor"),
        ("", "xx:yy,xx:", "", "empty label"),
        # Pending to prepare tests for multiple image labels when the functionality is implemented.
        ("", "zz:aa,xx:yy", "", "not yet implemented"),
    ],
)
def test_errror_flavor_config(
    monkeypatch,
    openstack_flavor,
    flavor_label_combinations,
    labels,
    expected_error_message,
):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm with the specified config options for the number
       of flavors and labels.
    assert: The exception CharmConfigInvalidError should be raised with the expected message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    monkeypatch.setattr(OpenstackImage, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())
    mock_charm.config[OPENSTACK_FLAVOR_CONFIG_NAME] = openstack_flavor
    mock_charm.config[FLAVOR_LABEL_COMBINATIONS_CONFIG_NAME] = flavor_label_combinations
    mock_charm.config[LABELS_CONFIG_NAME] = labels

    mock_database = MagicMock(spec=DatabaseRequires)
    with pytest.raises(CharmConfigInvalidError) as exc_info:
        _ = CharmState.from_charm(mock_charm, mock_database)
    assert expected_error_message in str(exc_info.value)


def test_charm_state__log_prev_state_redacts_sensitive_information(
    mock_charm_state_data: dict, caplog: pytest.LogCaptureFixture
):
    """
    arrange: Arrange charm state data with a token and set log level to DEBUG.
    act: Call the __log_prev_state method on the class.
    assert: Verify that the method redacts the sensitive information in the log message.
    """
    caplog.set_level(logging.DEBUG)
    CharmState._log_prev_state(mock_charm_state_data)

    assert mock_charm_state_data["charm_config"]["token"] not in caplog.text
    assert charm_state.SENSITIVE_PLACEHOLDER in caplog.text


@pytest.mark.parametrize(
    "juju_http, juju_https, juju_no_proxy, runner_http, use_aproxy,"
    "expected_proxy, expected_runner_proxy",
    [
        pytest.param(
            "", "", "", "", False, ProxyConfig(), ProxyConfig(), id="No proxy. No aproxy"
        ),
        pytest.param(
            "",
            "",
            "localhost",
            "",
            False,
            ProxyConfig(),
            ProxyConfig(),
            id="No proxy with only no_proxy. No aproxy",
        ),
        pytest.param(
            "http://example.com:3128",
            "",
            "",
            "",
            False,
            ProxyConfig(http="http://example.com:3128"),
            ProxyConfig(http="http://example.com:3128"),
            id="Only proxy from juju. No aproxy.",
        ),
        pytest.param(
            "http://manager.example.com:3128",
            "",
            "",
            "http://runner.example.com:3128",
            False,
            ProxyConfig(http="http://manager.example.com:3128"),
            ProxyConfig(http="http://runner.example.com:3128"),
            id="Both juju and runner proxy. No aproxy.",
        ),
        pytest.param(
            "",
            "",
            "",
            "http://runner.example.com:3128",
            True,
            ProxyConfig(),
            ProxyConfig(http="http://runner.example.com:3128"),
            id="Only proxy in runner. aproxy configured.",
        ),
        pytest.param(
            "http://manager.example.com:3128",
            "http://securemanager.example.com:3128",
            "127.0.0.1",
            "http://runner.example.com:3128",
            True,
            ProxyConfig(
                http="http://manager.example.com:3128",
                https="http://securemanager.example.com:3128",
                no_proxy="127.0.0.1",
            ),
            ProxyConfig(
                http="http://runner.example.com:3128",
            ),
            id="Proxy in juju and the runner. aproxy configured.",
        ),
    ],
)
def test_proxy_config(
    monkeypatch,
    juju_http: str,
    juju_https: str,
    juju_no_proxy: str,
    runner_http: str,
    use_aproxy: bool,
    expected_proxy: ProxyConfig,
    expected_runner_proxy: ProxyConfig,
):
    """
    arrange: Mock CharmBase and necessary methods.
    act: Call CharmState.from_charm with the specified config options for the manager proxy,
       the runner proxy and aproxy.
    assert: The expected proxies and aproxy information should be populated.
    """
    mock_charm = MockGithubRunnerCharmFactory()

    monkeypatch.setenv("JUJU_CHARM_HTTP_PROXY", juju_http)
    monkeypatch.setenv("JUJU_CHARM_HTTPS_PROXY", juju_https)
    monkeypatch.setenv("JUJU_CHARM_NO_PROXY", juju_no_proxy)
    mock_charm.config[USE_APROXY_CONFIG_NAME] = use_aproxy
    mock_charm.config[RUNNER_HTTP_PROXY_CONFIG_NAME] = runner_http

    mock_charm.model.relations[IMAGE_INTEGRATION_NAME] = []
    mock_database = MagicMock(spec=DatabaseRequires)
    mock_database.relations = []

    charm_state = CharmState.from_charm(mock_charm, mock_database)

    assert charm_state.charm_config.use_aproxy == use_aproxy
    assert charm_state.proxy_config == expected_proxy
    assert charm_state.runner_proxy_config == expected_runner_proxy
