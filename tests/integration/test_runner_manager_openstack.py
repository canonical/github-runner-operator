# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing the RunnerManager class with OpenStackRunnerManager as CloudManager."""


import pytest
import pytest_asyncio
import yaml
from openstack.connection import Connection as OpenstackConnection

from charm_state import GithubPath, ProxyConfig, parse_github_path
from manager.runner_manager import RunnerManager, RunnerManagerConfig
from openstack_cloud.openstack_cloud import _CLOUDS_YAML_PATH
from openstack_cloud.openstack_runner_manager import (
    OpenstackRunnerManager,
    OpenstackRunnerManagerConfig,
)
from tests.integration.helpers.openstack import PrivateEndpointConfigs


@pytest.fixture(scope="module", name="github_path")
def github_path_fixture(path: str) -> GithubPath:
    return parse_github_path(path, "Default")


@pytest.fixture(scope="module", name="proxy_config")
def openstack_proxy_config_fixture(
    openstack_http_proxy: str, openstack_https_proxy: str, openstack_no_proxy: str
) -> ProxyConfig:
    use_aproxy = False
    if openstack_http_proxy or openstack_https_proxy:
        use_aproxy = True
    openstack_http_proxy = openstack_http_proxy if openstack_http_proxy else None
    openstack_https_proxy = openstack_https_proxy if openstack_https_proxy else None
    return ProxyConfig(
        http=openstack_http_proxy,
        https=openstack_https_proxy,
        no_proxy=openstack_no_proxy,
        use_aproxy=use_aproxy,
    )


@pytest_asyncio.fixture(scope="module", name="openstack_runner_manager")
async def openstack_runner_manager_fixture(
    app_name: str,
    private_endpoint_clouds_yaml: str,
    openstack_test_image: str,
    flavor_name: str,
    network_name: str,
    github_path: GithubPath,
    proxy_config: ProxyConfig,
    openstack_connection: OpenstackConnection,
) -> OpenstackRunnerManager:
    """Create OpenstackRunnerManager instance.

    The prefix args of OpenstackRunnerManager set to app_name to let openstack_connection_fixture preform the cleanup of openstack resources.
    """
    # TODO: Think about how to deal with this when testing locally.
    # This will modify a file under home directory.
    _CLOUDS_YAML_PATH.unlink()
    clouds_config = yaml.safe_load(private_endpoint_clouds_yaml)

    config = OpenstackRunnerManagerConfig(
        clouds_config=clouds_config,
        cloud="testcloud",
        image=openstack_test_image,
        flavor=flavor_name,
        network=network_name,
        github_path=github_path,
        labels=["openstack_test"],
        proxy_config=proxy_config,
        dockerhub_mirror=None,
        ssh_debug_connections=None,
        repo_policy_url=None,
        repo_policy_token=None,
    )
    return OpenstackRunnerManager(app_name, config)


@pytest_asyncio.fixture(scope="module", name="runner_manager")
async def runner_manager_fixture(
    openstack_runner_manager: OpenstackRunnerManager, token: str, github_path: GithubPath
) -> RunnerManager:
    config = RunnerManagerConfig(token, github_path)
    return RunnerManager(openstack_runner_manager, config)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_get_no_runner(runner_manager: RunnerManager) -> None:
    """
    Arrange: No runners on the
    Act:
    Assert:
    """
    runner_list = runner_manager.get_runners()
    assert isinstance(runner_list, tuple)
    assert not runner_list
