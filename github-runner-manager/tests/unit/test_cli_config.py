#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test for the cli_config module."""

from pathlib import Path

import pydantic
import pytest
import yaml

from src.github_runner_manager.cli_config import Configuration

ConfigValue = None | int | bool | str | tuple
ConfigDict = dict[str, ConfigValue]


@pytest.fixture(name="sample_config")
def sample_config_fixture() -> ConfigDict:
    return {
        "name": "test_org/test_repo",
        "github_path": "test_org",
        "github_token": "test_token",
        "github_runner_group": None,
        "runner_count": 1,
        "runner_labels": ("test", "unit-test", "test-data"),
        "openstack_auth_url": "http://www.example.com/test_url",
        "openstack_project_name": "test-project",
        "openstack_username": "test-username",
        "openstack_password": "test-password",
        "openstack_user_domain_name": "default",
        "openstack_domain_name": "default",
        "openstack_flavor": "test_flavor",
        "openstack_network": "test_network",
        "dockerhub_mirror": None,
        "repo_policy_compliance_url": None,
        "repo_policy_compliance_token": None,
        "http_proxy": None,
        "no_proxy": None,
    }


def get_cli_configuration(config: dict[str, ConfigValue], file_path: Path) -> Configuration:
    """Get the Configuration object from given configuration dict.

    Args:
        config: A dict containing the configurations.
        file_path: The path to a temp file. The yaml module only support dump to stream, might as
            well use a temp file.

    Returns:
        The Configuration object created from the data in the dict.
    """
    with open(file_path, mode="w", encoding="utf-8") as file:
        yaml.safe_dump(config, file)

    with open(file_path, mode="r", encoding="utf-8") as file:
        return Configuration.from_yaml_file(file)


@pytest.fixture(name="tmp_yaml_file", scope="function")
def tmp_yaml_file_fixture(tmp_path: Path) -> Path:
    return tmp_path / "tmp_config.yaml"


def test_sample_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: None.
    act: Create the Configuration from SAMPLE_CONFIG.
    assert: The configuration content should match.
    """
    config = get_cli_configuration(sample_config, tmp_yaml_file)
    diff = set(config.dict().items()) ^ set(sample_config.items())
    assert not diff


def test_optional_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: Remove the optional entry in the SAMPLE_CONFIG.
    act: Create the configuration from config.
    assert: The configuration content should match.
    """
    config = dict(sample_config)
    config.pop("http_proxy")
    config.pop("no_proxy")
    config.pop("repo_policy_compliance_token")
    config.pop("repo_policy_compliance_url")
    config.pop("dockerhub_mirror")
    config.pop("github_runner_group")

    configuration = get_cli_configuration(config, tmp_yaml_file)
    diff = set(configuration.dict().items()) ^ set(sample_config.items())
    assert not diff


def test_missing_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: Get a list of required fields.
    act: Create the Configuration without a required field.
    assert: Error should be raised with field required message.
    """
    required_field = [
        "name",
        "github_path",
        "github_token",
        "runner_count",
        "runner_labels",
        "openstack_auth_url",
        "openstack_project_name",
        "openstack_username",
        "openstack_password",
        "openstack_user_domain_name",
        "openstack_domain_name",
        "openstack_flavor",
        "openstack_network",
    ]

    for field in required_field:
        config = dict(sample_config)
        config.pop(field)

        with pytest.raises(pydantic.error_wrappers.ValidationError) as err:
            get_cli_configuration(config, tmp_yaml_file)

        errors = err.value.errors()
        assert len(errors) == 1
        assert field in errors[0]["loc"]
        assert errors[0]["msg"] == "field required"


def test_string_min_length_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: Get a list of fields of type string with min_length restraints.
    act: Create the Configuration with empty string in the fields.
    assert: Errors should be raised.
    """
    min_length_field = [
        "name",
        "github_path",
        "github_token",
        "openstack_auth_url",
        "openstack_project_name",
        "openstack_username",
        "openstack_password",
        "openstack_user_domain_name",
        "openstack_domain_name",
        "openstack_flavor",
        "openstack_network",
        "repo_policy_compliance_url",
        "repo_policy_compliance_token",
        "http_proxy",
        "no_proxy",
    ]

    for field in min_length_field:
        config = dict(sample_config)
        config[field] = ""

        with pytest.raises(pydantic.error_wrappers.ValidationError) as err:
            get_cli_configuration(config, tmp_yaml_file)

        errors = err.value.errors()
        assert len(errors) == 1
        assert field in errors[0]["loc"]
        assert errors[0]["msg"] == "ensure this value has at least 1 characters"


def test_max_length_for_name_field_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: None.
    act: Create the Configuration with a name over 50 characters.
    assert: Errors should be raised.
    """
    sample_config["name"] = "a" * 51

    with pytest.raises(pydantic.error_wrappers.ValidationError) as err:
        get_cli_configuration(sample_config, tmp_yaml_file)

    errors = err.value.errors()
    assert len(errors) == 1
    assert "name" in errors[0]["loc"]
    assert errors[0]["msg"] == "ensure this value has at most 50 characters"


def test_negative_runner_count_field_config(tmp_yaml_file: Path, sample_config: ConfigDict):
    """
    arrange: None.
    act: Create the Configuration with a runner_count under 0.
    assert: An error should be raised.
    """
    sample_config["runner_count"] = -1

    with pytest.raises(pydantic.error_wrappers.ValidationError) as err:
        get_cli_configuration(sample_config, tmp_yaml_file)

    errors = err.value.errors()
    assert len(errors) == 1
    assert "runner_count" in errors[0]["loc"]
    assert errors[0]["msg"] == "ensure this value is greater than or equal to 0"
