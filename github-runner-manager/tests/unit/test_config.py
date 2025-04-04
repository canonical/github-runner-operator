#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the github-runner-manager application configuration."""


import json
from io import StringIO
from ipaddress import IPv4Address

import pytest
import yaml
from pydantic import MongoDsn

from src.github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    GitHubConfiguration,
    GitHubOrg,
    Image,
    NonReactiveCombination,
    NonReactiveConfiguration,
    ProxyConfig,
    QueueConfig,
    ReactiveConfiguration,
    RepoPolicyComplianceConfig,
    SSHDebugConnection,
    SupportServiceConfig,
)

SAMPLE_YAML_CONFIGURATION = """
name: app_name
extra_labels:
- label1
- label2
platform: github
platform_config:
  path:
    group: group
    org: canonical
  token: githubtoken
non_reactive_configuration:
  combinations:
  - base_virtual_machines: 1
    flavor:
      labels:
      - flavorlabel
      name: flavor
    image:
      labels:
      - arm64
      - noble
      name: image_id
reactive_configuration:
  flavors:
  - labels:
    - flavorlabel
    name: flavor
  images:
  - labels:
    - arm64
    - noble
    name: image_id
  max_total_virtual_machines: 2
  queue:
    mongodb_uri: mongodb://user:password@localhost:27017
    queue_name: app_name
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
  repo_policy_compliance:
    token: token
    url: https://compliance.example.com
  ssh_debug_connections:
  - ed25519_fingerprint: SHA256:ed25519
    host: 10.10.10.10
    port: 3000
    rsa_fingerprint: SHA256:rsa
"""


@pytest.fixture(name="app_config", scope="module")
def app_config_fixture() -> ApplicationConfiguration:
    # The type ignore is due type coercion from pydantic with convert the types.
    return ApplicationConfiguration(
        name="app_name",
        extra_labels=["label1", "label2"],
        platform="github",
        platform_config=GitHubConfiguration(
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
            repo_policy_compliance=RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",  # type: ignore
            ),
        ),
        non_reactive_configuration=NonReactiveConfiguration(
            combinations=[
                NonReactiveCombination(
                    image=Image(
                        name="image_id",
                        labels=["arm64", "noble"],
                    ),
                    flavor=Flavor(
                        name="flavor",
                        labels=["flavorlabel"],
                    ),
                    base_virtual_machines=1,
                )
            ]
        ),
        reactive_configuration=ReactiveConfiguration(
            queue=QueueConfig(
                mongodb_uri=MongoDsn(
                    "mongodb://user:password@localhost:27017",
                    scheme="mongodb",
                    user="user",
                    password="password",
                    host="localhost",
                    host_type="int_domain",
                    port="27017",
                ),
                queue_name="app_name",
            ),
            max_total_virtual_machines=2,
            images=[
                Image(name="image_id", labels=["arm64", "noble"]),
            ],
            flavors=[Flavor(name="flavor", labels=["flavorlabel"])],
        ),
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
    loaded_config = ApplicationConfiguration.validate(
        yaml.safe_load(StringIO(SAMPLE_YAML_CONFIGURATION))
    )
    assert app_config == loaded_config
