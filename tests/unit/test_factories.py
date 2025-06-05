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


@pytest.mark.parametrize(
    "with_github_config, expected_github_config",
    [
        pytest.param(
            True,
            GitHubConfiguration(
                token="githubtoken", path=GitHubOrg(org="canonical", group="group")
            ),
            id="with_github_config",
        ),
        pytest.param(False, None, id="without_github_config"),
    ],
)
def test_create_application_configuration(
    complete_charm_state: charm_state.CharmState,
    with_github_config: bool,
    expected_github_config: GitHubConfiguration | None,
):
    """
    arrange: Prepare a fully populated CharmState.
    act: Call create_application_configuration.
    assert: The ApplicationConfiguration is correctly populated.
    """
    state = complete_charm_state

    if not with_github_config:
        state.charm_config.path = None
        state.charm_config.token = None

    app_configuration = factories.create_application_configuration(state, "app_name", "unit_name")

    assert app_configuration == ApplicationConfiguration(
        name="app_name",
        extra_labels=["label1", "label2"],
        github_config=expected_github_config,
        service_config=SupportServiceConfig(
            manager_proxy_command="ssh -W %h:%p example.com",
            proxy_config=ProxyConfig(
                http="http://httpproxy.example.com:3128",
                https="http://httpsproxy.example.com:3128",
                no_proxy="127.0.0.1",
            ),
            runner_proxy_config=ProxyConfig(
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
                    use_runner_http_proxy=False,
                    local_proxy_host="127.0.0.1",
                    local_proxy_port=3129,
                )
            ],
            repo_policy_compliance=RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
        ),
        non_reactive_configuration=NonReactiveConfiguration(
            combinations=[
                NonReactiveCombination(
                    image=Image(name="image_id", labels=["arm64", "noble"]),
                    flavor=Flavor(name="flavor", labels=["flavorlabel"]),
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
            images=[Image(name="image_id", labels=["arm64", "noble"])],
            flavors=[Flavor(name="flavor", labels=["flavorlabel"])],
        ),
        openstack_configuration=OpenStackConfiguration(
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
        ),
        reconcile_interval=5,
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
