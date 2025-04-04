#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

import pytest
from github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
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
from github_runner_manager.configuration.github import GitHubConfiguration, GitHubOrg
from github_runner_manager.openstack_cloud.configuration import (
    OpenStackConfiguration,
    OpenStackCredentials,
)
from pydantic import MongoDsn
from pydantic.networks import IPv4Address

import charm_state
import factories


@pytest.fixture
def complete_charm_state():
    """Returns a fixture with a fully populated CharmState."""
    return charm_state.CharmState(
        arch="arm64",
        is_metrics_logging_available=False,
        proxy_config=charm_state.ProxyConfig(
            http="http://httpproxy.example.com:3128",
            https="http://httpsproxy.example.com:3128",
            no_proxy="127.0.0.1",
        ),
        runner_proxy_config=charm_state.ProxyConfig(
            http="http://runnerhttpproxy.example.com:3128",
            https="http://runnerhttpsproxy.example.com:3128",
            no_proxy="10.0.0.1",
        ),
        charm_config=charm_state.CharmConfig(
            dockerhub_mirror="https://docker.example.com",
            labels=("label1", "label2"),
            openstack_clouds_yaml=charm_state.OpenStackCloudsYAML(
                clouds={
                    "microstack": {
                        "auth": {
                            "auth_url": "auth_url",
                            "project_name": "project_name",
                            "project_domain_name": "project_domain_name",
                            "username": "username",
                            "user_domain_name": "user_domain_name",
                            "password": "password",
                        },
                        "region_name": "region",
                    }
                },
            ),
            platform="github",
            platform_config=GitHubConfiguration(token="githubtoken", path=GitHubOrg(org="canonical", group="group")),
            reconcile_interval=5,
            repo_policy_compliance=charm_state.RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
            manager_proxy_command="ssh -W %h:%p example.com",
            use_aproxy=True,
        ),
        runner_config=charm_state.OpenstackRunnerConfig(
            base_virtual_machines=1,
            max_total_virtual_machines=2,
            flavor_label_combinations=[
                charm_state.FlavorLabel(
                    flavor="flavor",
                    label="flavorlabel",
                )
            ],
            openstack_network="network",
            openstack_image=charm_state.OpenstackImage(
                id="image_id",
                tags=["arm64", "noble"],
            ),
        ),
        reactive_config=charm_state.ReactiveConfig(
            mq_uri="mongodb://user:password@localhost:27017",
        ),
        ssh_debug_connections=[
            charm_state.SSHDebugConnection(
                host="10.10.10.10",
                port=3000,
                # Not very realistic
                rsa_fingerprint="SHA256:rsa",
                ed25519_fingerprint="SHA256:ed25519",
            ),
        ],
    )


def test_create_application_configuration(complete_charm_state: charm_state.CharmState):
    """
    arrange: Prepare a fully populated CharmState.
    act: Call create_application_configuration.
    assert: The ApplicationConfiguration is correctly populated.
    """
    state = complete_charm_state

    app_configuration = factories.create_application_configuration(state, "app_name")

    assert app_configuration == ApplicationConfiguration(
        name="app_name",
        extra_labels=["label1", "label2"],
        platform="github",
        platform_config=GitHubConfiguration(
            token="githubtoken", path=GitHubOrg(org="canonical", group="group")
        ),
        service_config=SupportServiceConfig(
            proxy_config=ProxyConfig(
                http="http://httpproxy.example.com:3128",
                https="http://httpsproxy.example.com:3128",
                no_proxy="127.0.0.1",
            ),
            runner_proxy_config=charm_state.ProxyConfig(
                http="http://runnerhttpproxy.example.com:3128",
                https="http://runnerhttpsproxy.example.com:3128",
                no_proxy="10.0.0.1",
            ),
            use_aproxy=True,
            dockerhub_mirror="https://docker.example.com",
            ssh_debug_connections=[
                SSHDebugConnection(
                    host=IPv4Address("10.10.10.10"),
                    port=3000,
                    rsa_fingerprint="SHA256:rsa",
                    ed25519_fingerprint="SHA256:ed25519",
                )
            ],
            repo_policy_compliance=RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
            manager_proxy_command="ssh -W %h:%p example.com",
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


def test_create_openstack_configuration(complete_charm_state: charm_state.CharmState):
    """
    arrange: Prepare a fully populated CharmState.
    act: Call create_openstack_configuration.
    assert: The OpenStackConfiguration is correctly populated.
    """
    state = complete_charm_state

    openstack_configuration = factories.create_openstack_configuration(state, "unit_name")

    assert openstack_configuration == OpenStackConfiguration(
        vm_prefix="unit_name",
        network="network",
        credentials=OpenStackCredentials(
            auth_url="auth_url",
            project_name="project_name",
            username="username",
            password="password",
            user_domain_name="user_domain_name",
            project_domain_name="project_domain_name",
            region_name="region",
        ),
    )
