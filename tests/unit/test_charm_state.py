# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import platform
import typing
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from pydantic import BaseModel
from pydantic.error_wrappers import ValidationError
from pydantic.networks import IPv4Address

import charm_state
import openstack_cloud
from charm_state import (
    BASE_IMAGE_CONFIG_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    DENYLIST_CONFIG_NAME,
    DOCKERHUB_MIRROR_CONFIG_NAME,
    IMAGE_INTEGRATION_NAME,
    LABELS_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    RUNNER_STORAGE_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    VM_CPU_CONFIG_NAME,
    VM_DISK_CONFIG_NAME,
    VM_MEMORY_CONFIG_NAME,
    Arch,
    BaseImage,
    CharmConfig,
    CharmConfigInvalidError,
    CharmState,
    FirewallEntry,
    GithubConfig,
    GithubOrg,
    GithubRepo,
    ImmutableConfigChangedError,
    LocalLxdRunnerConfig,
    OpenstackImage,
    OpenstackRunnerConfig,
    ProxyConfig,
    RunnerStorage,
    SSHDebugConnection,
    UnsupportedArchitectureError,
    VirtualMachineResources,
)
from errors import MissingIntegrationDataError
from tests.unit.factories import MockGithubRunnerCharmFactory


def test_github_repo_path():
    """
    arrange: Create a GithubRepo instance with owner and repo attributes.
    act: Call the path method of the GithubRepo instance with a mock.
    assert: Verify that the returned path is constructed correctly.
    """
    owner = "test_owner"
    repo = "test_repo"
    github_repo = GithubRepo(owner, repo)

    path = github_repo.path()

    assert path == f"{owner}/{repo}"


def test_github_org_path():
    """
    arrange: Create a GithubOrg instance with org and group attributes.
    act: Call the path method of the GithubOrg instance.
    assert: Verify that the returned path is constructed correctly.
    """
    org = "test_org"
    group = "test_group"
    github_org = GithubOrg(org, group)

    path = github_org.path()

    assert path == org


def test_parse_github_path_invalid():
    """
    arrange: Create an invalid GitHub path string and runner group name.
    act: Call parse_github_path with the invalid path string and runner group name.
    assert: Verify that the function raises CharmConfigInvalidError.
    """
    path_str = "invalidpath/"
    runner_group = "test_group"

    with pytest.raises(CharmConfigInvalidError):
        charm_state.parse_github_path(path_str, runner_group)


def test_github_config_from_charm_invalid_path():
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
        ("owner/repo", "test_group", GithubRepo, {"owner": "owner", "repo": "repo"}),
        ("test_org", "test_group", GithubOrg, {"org": "test_org", "group": "test_group"}),
    ],
)
def test_parse_github_path(
    path_str: str,
    runner_group: str,
    expected_type: GithubRepo | GithubOrg,
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


@pytest.mark.parametrize(
    "denylist_config, expected_entries",
    [
        ("", []),
        ("192.168.1.1", [FirewallEntry(ip_range="192.168.1.1")]),
        (
            "192.168.1.1, 192.168.1.2, 192.168.1.3",
            [
                FirewallEntry(ip_range="192.168.1.1"),
                FirewallEntry(ip_range="192.168.1.2"),
                FirewallEntry(ip_range="192.168.1.3"),
            ],
        ),
    ],
)
def test_parse_denylist(denylist_config: str, expected_entries: typing.List[FirewallEntry]):
    """
    arrange: Create a mock CharmBase instance with provided denylist configuration.
    act: Call _parse_denylist method with the mock CharmBase instance.
    assert: Verify that the method returns the expected list of FirewallEntry objects.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[DENYLIST_CONFIG_NAME] = denylist_config

    result = CharmConfig._parse_denylist(mock_charm)

    assert result == expected_entries


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
    assert: Verify that the method returns None.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = ""

    result = CharmConfig._parse_openstack_clouds_config(mock_charm)

    assert result is None


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


def test_parse_openstack_clouds_initialize_fail(
    valid_yaml_config: str, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given monkeypatched openstack_cloud.initialize that raises an error.
    act: Call _parse_openstack_clouds_config method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = valid_yaml_config
    monkeypatch.setattr(
        openstack_cloud,
        "initialize",
        MagicMock(side_effect=openstack_cloud.OpenStackInvalidConfigError),
    )

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
        DENYLIST_CONFIG_NAME: "192.168.1.1,192.168.1.2",
        DOCKERHUB_MIRROR_CONFIG_NAME: "https://example.com",
        OPENSTACK_CLOUDS_YAML_CONFIG_NAME: "clouds: { openstack: { auth: { username: 'admin' }}}",
        LABELS_CONFIG_NAME: "label1,label2,label3",
        TOKEN_CONFIG_NAME: "abc123",
    }

    result = CharmConfig.from_charm(mock_charm)

    assert result.path == GithubRepo(owner="owner", repo="repo")
    assert result.reconcile_interval == 5
    assert result.denylist == [
        FirewallEntry(ip_range="192.168.1.1"),
        FirewallEntry(ip_range="192.168.1.2"),
    ]
    assert result.dockerhub_mirror == "https://example.com"
    assert result.openstack_clouds_yaml == {
        "clouds": {"openstack": {"auth": {"username": "admin"}}}
    }
    assert result.labels == ("label1", "label2", "label3")
    assert result.token == "abc123"


@pytest.mark.parametrize(
    "base_image, expected_str",
    [
        (BaseImage.JAMMY, "jammy"),
        (BaseImage.NOBLE, "noble"),
    ],
)
def test_base_image_str_parametrized(base_image, expected_str):
    """
    Parametrized test case for __str__ method of BaseImage enum.

    arrange: Pass BaseImage enum values and expected string.
    act: Call __str__ method on each enum value.
    assert: Ensure the returned string matches the expected string.
    """
    assert str(base_image) == expected_str


def test_base_image_from_charm_invalid_image():
    """
    arrange: Create a mock CharmBase instance with an invalid base image configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises an error.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[BASE_IMAGE_CONFIG_NAME] = "invalid"

    with pytest.raises(ValueError):
        BaseImage.from_charm(mock_charm)


@pytest.mark.parametrize(
    "image_name, expected_result",
    [
        ("noble", BaseImage.NOBLE),  # Valid custom configuration "noble"
        ("24.04", BaseImage.NOBLE),  # Valid custom configuration "noble"
        ("jammy", BaseImage.JAMMY),  # Valid custom configuration "jammy"
        ("22.04", BaseImage.JAMMY),  # Valid custom configuration "jammy"
    ],
)
def test_base_image_from_charm(image_name: str, expected_result: BaseImage):
    """
    arrange: Create a mock CharmBase instance with the provided image_name configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method returns the expected base image tag.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[BASE_IMAGE_CONFIG_NAME] = image_name

    result = BaseImage.from_charm(mock_charm)

    assert result == expected_result


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


@pytest.mark.parametrize("virtual_machines", [(-1), (-5)])  # Invalid value  # Invalid value
def test_check_virtual_machines_invalid(virtual_machines):
    """
    arrange: Provide an invalid virtual machines value.
    act: Call check_virtual_machines method with the provided value.
    assert: Verify that the method raises ValueError with the correct message.
    """
    with pytest.raises(ValueError) as exc_info:
        LocalLxdRunnerConfig.check_virtual_machines(virtual_machines)
    assert (
        str(exc_info.value)
        == "The virtual-machines configuration needs to be greater or equal to 0"
    )


@pytest.mark.parametrize(
    "virtual_machines", [(0), (5), (10)]  # Minimum valid value  # Valid value  # Valid value
)
def test_check_virtual_machines_valid(virtual_machines):
    """
    arrange: Provide a valid virtual machines value.
    act: Call check_virtual_machines method with the provided value.
    assert: Verify that the method returns the same value.
    """
    result = LocalLxdRunnerConfig.check_virtual_machines(virtual_machines)

    assert result == virtual_machines


@pytest.mark.parametrize(
    "vm_resources",
    [
        VirtualMachineResources(cpu=0, memory="1GiB", disk="10GiB"),  # Invalid CPU value
        VirtualMachineResources(cpu=1, memory="invalid", disk="10GiB"),  # Invalid memory value
        VirtualMachineResources(cpu=1, memory="1GiB", disk="invalid"),  # Invalid disk value
    ],
)
def test_check_virtual_machine_resources_invalid(vm_resources):
    """
    arrange: Provide an invalid virtual_machine_resources value.
    act: Call check_virtual_machine_resources method with the provided value.
    assert: Verify that the method raises ValueError.
    """
    with pytest.raises(ValueError):
        LocalLxdRunnerConfig.check_virtual_machine_resources(vm_resources)


@pytest.mark.parametrize(
    "vm_resources, expected_result",
    [
        (
            VirtualMachineResources(cpu=1, memory="1GiB", disk="10GiB"),
            VirtualMachineResources(cpu=1, memory="1GiB", disk="10GiB"),
        ),  # Valid configuration
        (
            VirtualMachineResources(cpu=2, memory="2GiB", disk="20GiB"),
            VirtualMachineResources(cpu=2, memory="2GiB", disk="20GiB"),
        ),  # Valid configuration
    ],
)
def test_check_virtual_machine_resources_valid(vm_resources, expected_result):
    """
    arrange: Provide a valid virtual_machine_resources value.
    act: Call check_virtual_machine_resources method with the provided value.
    assert: Verify that the method returns the same value.
    """
    result = LocalLxdRunnerConfig.check_virtual_machine_resources(vm_resources)

    assert result == expected_result


def test_runner_charm_config_from_charm_invalid_base_image():
    """
    arrange: Create a mock CharmBase instance with an invalid base image configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config[BASE_IMAGE_CONFIG_NAME] = "invalid"

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        LocalLxdRunnerConfig.from_charm(mock_charm)
    assert str(exc_info.value) == "Invalid base image"


def test_runner_charm_config_from_charm_invalid_storage_config():
    """
    arrange: Create a mock CharmBase instance with an invalid storage configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config = {
        BASE_IMAGE_CONFIG_NAME: "jammy",
        RUNNER_STORAGE_CONFIG_NAME: "invalid",
        VIRTUAL_MACHINES_CONFIG_NAME: "5",
        VM_CPU_CONFIG_NAME: "2",
        VM_MEMORY_CONFIG_NAME: "4GiB",
        VM_DISK_CONFIG_NAME: "20GiB",
    }

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        LocalLxdRunnerConfig.from_charm(mock_charm)
    assert "Invalid runner-storage config" in str(exc_info.value)


def test_runner_charm_config_from_charm_invalid_cpu_config():
    """
    arrange: Create a mock CharmBase instance with an invalid cpu configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config = {
        BASE_IMAGE_CONFIG_NAME: "jammy",
        RUNNER_STORAGE_CONFIG_NAME: "memory",
        VIRTUAL_MACHINES_CONFIG_NAME: "5",
        VM_CPU_CONFIG_NAME: "invalid",
        VM_MEMORY_CONFIG_NAME: "4GiB",
        VM_DISK_CONFIG_NAME: "20GiB",
    }

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        LocalLxdRunnerConfig.from_charm(mock_charm)
    assert str(exc_info.value) == "Invalid vm-cpu configuration"


def test_runner_charm_config_from_charm_invalid_virtual_machines_config():
    """
    arrange: Create a mock CharmBase instance with an invalid virtual machines configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method raises CharmConfigInvalidError with the correct message.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config = {
        BASE_IMAGE_CONFIG_NAME: "jammy",
        RUNNER_STORAGE_CONFIG_NAME: "memory",
        VIRTUAL_MACHINES_CONFIG_NAME: "invalid",
        VM_CPU_CONFIG_NAME: "2",
        VM_MEMORY_CONFIG_NAME: "4GiB",
        VM_DISK_CONFIG_NAME: "20GiB",
    }

    with pytest.raises(CharmConfigInvalidError) as exc_info:
        LocalLxdRunnerConfig.from_charm(mock_charm)
    assert str(exc_info.value) == "The virtual-machines configuration must be int"


def test_runner_charm_config_from_charm_valid():
    """
    arrange: Create a mock CharmBase instance with valid configuration.
    act: Call from_charm method with the mock CharmBase instance.
    assert: Verify that the method returns a LocalLxdRunnerConfig instance with the expected
        values.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    mock_charm.config = {
        BASE_IMAGE_CONFIG_NAME: "jammy",
        RUNNER_STORAGE_CONFIG_NAME: "memory",
        VIRTUAL_MACHINES_CONFIG_NAME: "5",
        VM_CPU_CONFIG_NAME: "2",
        VM_MEMORY_CONFIG_NAME: "4GiB",
        VM_DISK_CONFIG_NAME: "20GiB",
    }

    result = LocalLxdRunnerConfig.from_charm(mock_charm)

    assert result.base_image == BaseImage.JAMMY
    assert result.runner_storage == RunnerStorage("memory")
    assert result.virtual_machines == 5
    assert result.virtual_machine_resources == VirtualMachineResources(
        cpu=2, memory="4GiB", disk="20GiB"
    )


@pytest.mark.parametrize(
    "http, https, use_aproxy, expected_address",
    [
        ("http://proxy.example.com", None, True, "proxy.example.com"),
        (None, "https://secureproxy.example.com", True, "secureproxy.example.com"),
        (None, None, False, None),
        ("http://proxy.example.com", None, False, None),
    ],
)
def test_apropy_address(
    http: str | None, https: str | None, use_aproxy: bool, expected_address: str | None
):
    """
    arrange: Create a ProxyConfig instance with specified HTTP, HTTPS, and aproxy settings.
    act: Access the aproxy_address property of the ProxyConfig instance.
    assert: Verify that the property returns the expected apropy address.
    """
    proxy_config = ProxyConfig(http=http, https=https, use_aproxy=use_aproxy)

    result = proxy_config.aproxy_address

    assert result == expected_address


def test_check_use_aproxy():
    """
    arrange: Create a dictionary of values representing a proxy configuration with use_aproxy set\
        to True but neither http nor https provided.
    act: Call the check_use_aproxy method with the provided values.
    assert: Verify that the method raises a ValueError with the expected message.
    """
    values = {"http": None, "https": None}
    use_aproxy = True

    with pytest.raises(ValueError) as exc_info:
        ProxyConfig.check_use_aproxy(use_aproxy, values)

    assert str(exc_info.value) == "aproxy requires http or https to be set"


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

    result = ProxyConfig.from_charm(mock_charm)

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

    connections = SSHDebugConnection.from_charm(mock_charm)

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

    connections = SSHDebugConnection.from_charm(mock_charm)

    assert not connections


def test_ssh_debug_connection_from_charm():
    """
    arrange: Mock CharmBase instance with relation data.
    act: Call SSHDebugConnection.from_charm method.
    assert: Verify that the method returns the expected list of SSHDebugConnection instances.
    """
    mock_charm = MockGithubRunnerCharmFactory()
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

    connections = SSHDebugConnection.from_charm(mock_charm)

    assert isinstance(connections[0], SSHDebugConnection)
    assert connections[0].host == IPv4Address("192.168.0.1")
    assert connections[0].port == 22
    assert connections[0].rsa_fingerprint == "SHA256:abcdef"
    assert connections[0].ed25519_fingerprint == "SHA256:ghijkl"


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

    with pytest.raises(MissingIntegrationDataError) as exc:
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
        "charm_config": {"denylist": ["192.168.1.1"], "token": "abc123"},
        "reactive_config": {"uri": "mongodb://user:password@localhost:27017"},
        "runner_config": {
            "base_image": "jammy",
            "virtual_machines": 2,
            "runner_storage": "memory",
        },
        "instance_type": "local-lxd",
        "ssh_debug_connections": [
            {"host": "10.1.2.4", "port": 22},
        ],
    }


@pytest.mark.parametrize(
    "immutable_config",
    [
        pytest.param("runner_storage", id="Runner storage"),
        pytest.param("base_image", id="Base image"),
    ],
)
def test_check_immutable_config_key_error(
    mock_charm_state_path: Path,
    mock_charm_state_data: dict[str, typing.Any],
    immutable_config: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: Mock CHARM_STATE_PATH and read_text method to return modified immutable config values.
    act: Call _check_immutable_config_change method.
    assert: None is returned.
    """
    mock_charm_state_data["runner_config"].pop(immutable_config)
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", mock_charm_state_path)
    monkeypatch.setattr(
        charm_state.CHARM_STATE_PATH,
        "read_text",
        MagicMock(return_value=json.dumps(mock_charm_state_data)),
    )

    assert CharmState._check_immutable_config_change(RunnerStorage.MEMORY, BaseImage.JAMMY) is None
    assert any(
        f"Key {immutable_config} not found, this will be updated to current config." in message
        for message in caplog.messages
    )


def test_check_immutable_config_change_no_previous_state(
    mock_charm_state_path: Path, mock_charm_state_data: dict, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock CHARM_STATE_PATH and read_text method to return no previous state.
    act: Call _check_immutable_config_change method.
    assert: Ensure no exception is raised.
    """
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", mock_charm_state_path)
    monkeypatch.setattr(charm_state.CHARM_STATE_PATH, "exists", MagicMock(return_value=False))
    state = CharmState(**mock_charm_state_data)

    assert state._check_immutable_config_change("new_runner_storage", "new_base_image") is None


def test_check_immutable_config_change_storage_changed(
    mock_charm_state_path: Path, mock_charm_state_data: dict, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock CHARM_STATE_PATH and read_text method to return previous state with different \
        storage.
    act: Call _check_immutable_config_change method.
    assert: Ensure ImmutableConfigChangedError is raised.
    """
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", mock_charm_state_path)
    monkeypatch.setattr(
        charm_state.CHARM_STATE_PATH,
        "read_text",
        MagicMock(return_value=json.dumps(mock_charm_state_data)),
    )
    state = CharmState(**mock_charm_state_data)

    with pytest.raises(ImmutableConfigChangedError):
        state._check_immutable_config_change(RunnerStorage.JUJU_STORAGE, BaseImage.JAMMY)


def test_check_immutable_config_change_base_image_changed(
    mock_charm_state_path, mock_charm_state_data, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock CHARM_STATE_PATH and read_text method to return previous state with different \
        base image.
    act: Call _check_immutable_config_change method.
    assert: Ensure ImmutableConfigChangedError is raised.
    """
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", mock_charm_state_path)
    monkeypatch.setattr(
        charm_state.CHARM_STATE_PATH,
        "read_text",
        MagicMock(return_value=json.dumps(mock_charm_state_data)),
    )
    state = CharmState(**mock_charm_state_data)

    with pytest.raises(ImmutableConfigChangedError):
        state._check_immutable_config_change(RunnerStorage.MEMORY, BaseImage.NOBLE)


def test_check_immutable_config(
    mock_charm_state_path, mock_charm_state_data, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock CHARM_STATE_PATH and read_text method to return previous state with same config.
    act: Call _check_immutable_config_change method.
    assert: None is returned.
    """
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", mock_charm_state_path)
    monkeypatch.setattr(
        charm_state.CHARM_STATE_PATH,
        "read_text",
        MagicMock(return_value=json.dumps(mock_charm_state_data)),
    )
    state = CharmState(**mock_charm_state_data)

    assert state._check_immutable_config_change(RunnerStorage.MEMORY, BaseImage.JAMMY) is None


class MockModel(BaseModel):
    """A Mock model class used for pydantic error testing."""


@pytest.mark.parametrize(
    "module, target, exc",
    [
        (
            ProxyConfig,
            "from_charm",
            ValidationError([], MockModel),
        ),
        (ProxyConfig, "from_charm", ValueError),
        (
            CharmState,
            "_check_immutable_config_change",
            ImmutableConfigChangedError("Immutable config changed"),
        ),
        (CharmConfig, "from_charm", ValidationError([], MockModel)),
        (CharmConfig, "from_charm", ValueError),
        (charm_state, "_get_supported_arch", UnsupportedArchitectureError(arch="testarch")),
        (SSHDebugConnection, "from_charm", ValidationError([], MockModel)),
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
    monkeypatch.setattr(ProxyConfig, "from_charm", MagicMock())
    mock_charm_config = MagicMock()
    mock_charm_config.openstack_clouds_yaml = None
    mock_charm_config_from_charm = MagicMock()
    mock_charm_config_from_charm.return_value = mock_charm_config
    monkeypatch.setattr(CharmConfig, "from_charm", mock_charm_config_from_charm)
    monkeypatch.setattr(OpenstackRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(LocalLxdRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(charm_state, "_get_supported_arch", MagicMock())
    monkeypatch.setattr(SSHDebugConnection, "from_charm", MagicMock())
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
    monkeypatch.setattr(ProxyConfig, "from_charm", MagicMock())
    monkeypatch.setattr(CharmConfig, "from_charm", MagicMock())
    monkeypatch.setattr(OpenstackRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(LocalLxdRunnerConfig, "from_charm", MagicMock())
    monkeypatch.setattr(CharmState, "_check_immutable_config_change", MagicMock())
    monkeypatch.setattr(charm_state, "_get_supported_arch", MagicMock())
    monkeypatch.setattr(charm_state, "ReactiveConfig", MagicMock())
    monkeypatch.setattr(SSHDebugConnection, "from_charm", MagicMock())
    monkeypatch.setattr(json, "loads", MagicMock())
    monkeypatch.setattr(json, "dumps", MagicMock())
    monkeypatch.setattr(charm_state, "CHARM_STATE_PATH", MagicMock())

    assert CharmState.from_charm(mock_charm, mock_database)
