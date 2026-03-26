#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the github-runner-manager application configuration."""

import json
from io import StringIO
from ipaddress import IPv4Address

import pytest
import yaml

from src.github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    GitHubConfiguration,
    GitHubOrg,
    Image,
    ProxyConfig,
    RunnerCombination,
    RunnerConfiguration,
    SSHDebugConnection,
    SupportServiceConfig,
)
from src.github_runner_manager.openstack_cloud.configuration import (
    OpenStackConfiguration,
    OpenStackCredentials,
)

SAMPLE_YAML_CONFIGURATION = """
name: app_name
extra_labels:
- label1
- label2
github_config:
  path:
    group: group
    org: canonical
  token: githubtoken
runner_configuration:
  combinations:
  - base_virtual_machines: 1
    max_total_virtual_machines: 2
    flavor:
      labels:
      - flavorlabel
      name: flavor
    image:
      labels:
      - arm64
      - noble
      name: image_id
service_config:
  dockerhub_mirror: https://docker.example.com
  proxy_config:
    http: http://httpproxy.example.com:3128
    https: http://httpsproxy.example.com:3128
    no_proxy: 127.0.0.1
  runner_proxy_config:
    http: http://httprunnerproxy.example.com:3128
    https: http://httpsrunnerproxy.example.com:3128
    no_proxy: 127.0.0.1
  use_aproxy: false
  ssh_debug_connections:
  - ed25519_fingerprint: SHA256:ed25519
    host: 10.10.10.10
    port: 3000
    rsa_fingerprint: SHA256:rsa
openstack_configuration:
    credentials:
      auth_url: http://example.com/test
      password: test_password
      project_domain_name: test_project_domain_name
      project_name: test_project
      region_name: test_region
      user_domain_name: test_user_domain_name
      username: test_username
    network: test_network
    vm_prefix: test_unit
planner_token: planner-testing-token
planner_url: http://planner.example.com
reconcile_interval: 10
"""


@pytest.fixture(name="app_config", scope="module")
def app_config_fixture() -> ApplicationConfiguration:
    # The type ignore is due type coercion from pydantic with convert the types.
    return ApplicationConfiguration(
        name="app_name",
        extra_labels=["label1", "label2"],
        github_config=GitHubConfiguration(
            token="githubtoken", path=GitHubOrg(org="canonical", group="group")
        ),
        service_config=SupportServiceConfig(
            proxy_config=ProxyConfig(
                http="http://httpproxy.example.com:3128",  # type: ignore
                https="http://httpsproxy.example.com:3128",  # type: ignore
                no_proxy="127.0.0.1",
            ),
            runner_proxy_config=ProxyConfig(
                http="http://httprunnerproxy.example.com:3128",  # type: ignore
                https="http://httpsrunnerproxy.example.com:3128",  # type: ignore
                no_proxy="127.0.0.1",
            ),
            use_aproxy=False,
            dockerhub_mirror="https://docker.example.com",
            ssh_debug_connections=[
                SSHDebugConnection(
                    host=IPv4Address("10.10.10.10"),  # type: ignore
                    port=3000,
                    rsa_fingerprint="SHA256:rsa",
                    ed25519_fingerprint="SHA256:ed25519",
                )
            ],
        ),
        runner_configuration=RunnerConfiguration(
            combinations=[
                RunnerCombination(
                    image=Image(
                        name="image_id",
                        labels=["arm64", "noble"],
                    ),
                    flavor=Flavor(
                        name="flavor",
                        labels=["flavorlabel"],
                    ),
                    base_virtual_machines=1,
                    max_total_virtual_machines=2,
                )
            ]
        ),
        openstack_configuration=OpenStackConfiguration(
            vm_prefix="test_unit",
            network="test_network",
            credentials=OpenStackCredentials(
                auth_url="http://example.com/test",
                project_name="test_project",
                username="test_username",
                password="test_password",
                user_domain_name="test_user_domain_name",
                project_domain_name="test_project_domain_name",
                region_name="test_region",
            ),
        ),
        planner_token="planner-testing-token",
        planner_url="http://planner.example.com",
        reconcile_interval=10,
    )


def test_configuration_roundtrip(app_config: ApplicationConfiguration):
    """
    arrange: A sample ApplicationConfiguration.
    act: Convert to json then back to ApplicationConfiguration.
    assert: The data should be the same.
    """
    # Using JSON as it is easier to convert from pydantic.BaseModel to JSON.
    # Both JSON and YAML is represented as dict in Python.
    reloaded_config = ApplicationConfiguration.validate(json.loads(app_config.json()))
    assert app_config == reloaded_config


def test_load_configuration_from_yaml(app_config: ApplicationConfiguration):
    """
    arrange: A sample configuration in YAML format.
    act: Get the ApplicationConfiguration object.
    assert: The content matches.
    """
    yaml_config = yaml.safe_load(StringIO(SAMPLE_YAML_CONFIGURATION))
    loaded_app_config = ApplicationConfiguration.validate(yaml_config)
    assert loaded_app_config == app_config


def test_runner_combination_rejects_max_below_base():
    """
    arrange: A RunnerCombination where max_total_virtual_machines < base_virtual_machines.
    act: Construct the model.
    assert: A ValidationError is raised.
    """
    with pytest.raises(
        ValueError, match="max_total_virtual_machines.*must be.*base_virtual_machines"
    ):
        RunnerCombination(
            image=Image(name="img", labels=[]),
            flavor=Flavor(name="flv", labels=[]),
            base_virtual_machines=5,
            max_total_virtual_machines=3,
        )


def test_runner_combination_allows_zero_max():
    """
    arrange: A RunnerCombination where max_total_virtual_machines is 0 (no cap).
    act: Construct the model.
    assert: No error is raised.
    """
    combo = RunnerCombination(
        image=Image(name="img", labels=[]),
        flavor=Flavor(name="flv", labels=[]),
        base_virtual_machines=5,
        max_total_virtual_machines=0,
    )
    assert combo.max_total_virtual_machines == 0


def test_configuration_allows_empty_planner_fields():
    """Planner URL/token are optional for non-planner mode."""
    config = yaml.safe_load(StringIO(SAMPLE_YAML_CONFIGURATION))
    config["planner_url"] = None
    config["planner_token"] = None

    loaded = ApplicationConfiguration.validate(config)

    assert loaded.planner_url is None
    assert loaded.planner_token is None
