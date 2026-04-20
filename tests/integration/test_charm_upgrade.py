#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for charm upgrades."""

import functools
import pathlib

import jubilant
import pytest

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    OPENSTACK_NETWORK_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
)
from tests.integration.conftest import (
    DeploymentContext,
    GitHubConfig,
    OpenStackConfig,
    ProxyConfig,
)
from tests.integration.helpers.common import (
    deploy_github_runner_charm,
    is_upgrade_charm_event_emitted,
    wait_for,
)

pytestmark = pytest.mark.openstack


@pytest.mark.skip(
    reason=(
        "latest/edge charm predates token-secret-id and openstack-clouds-yaml-secret-id "
        "config options. Falling back to the plaintext token/openstack-clouds-yaml options "
        "is not acceptable because jubilant logs deploy config, which leaks the token. "
        "Re-enable once a release containing the secret-id options has been promoted to "
        "latest/edge."
    )
)
def test_charm_upgrade(
    juju: jubilant.Juju,
    deployment_context: DeploymentContext,
    app_name: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    tmp_path: pathlib.Path,
    image_builder: str,
):
    """
    arrange: given latest edge version of the charm.
    act: charm upgrade is called.
    assert: the charm is upgraded successfully.
    """
    latest_edge_path = tmp_path / "github-runner.charm"
    # download the charm
    try:
        juju.cli(
            "download",
            "github-runner",
            # do not specify revision
            # --revision cannot be specified together with --arch, --base, --channel
            "--channel",
            "latest/edge",
            "--base",
            "ubuntu@22.04",
            "--filepath",
            str(latest_edge_path),
            "--no-progress",
            include_model=False,
        )
    except jubilant.CLIError as exc:
        pytest.fail(f"failed to download charm, {exc}")

    # deploy latest edge version of the charm
    deployed_name = deploy_github_runner_charm(
        juju=juju,
        charm_file=str(latest_edge_path),
        app_name=app_name,
        github_config=github_config,
        proxy_config=ProxyConfig(
            http_proxy=openstack_config.http_proxy,
            https_proxy=openstack_config.https_proxy,
            no_proxy=openstack_config.no_proxy,
        ),
        reconcile_interval=5,
        openstack_clouds_yaml=openstack_config.clouds_yaml_contents,
        config={
            OPENSTACK_NETWORK_CONFIG_NAME: openstack_config.network_name,
            OPENSTACK_FLAVOR_CONFIG_NAME: openstack_config.flavor_name,
            USE_APROXY_CONFIG_NAME: "true",
            VIRTUAL_MACHINES_CONFIG_NAME: 0,
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: 1,
        },
        wait_idle=False,
    )
    juju.integrate(image_builder, f"{deployed_name}:image")
    juju.wait(
        lambda status: jubilant.all_active(status, deployed_name, image_builder),
        timeout=25 * 60,
    )

    # upgrade the charm with current local charm
    juju.refresh(deployed_name, path=deployment_context.charm_path)

    unit_name = f"{deployed_name}/0"
    wait_for(
        functools.partial(is_upgrade_charm_event_emitted, juju, unit_name),
        timeout=360,
        check_interval=60,
    )
    juju.wait(
        lambda status: jubilant.all_active(status, deployed_name),
        timeout=20 * 60,
    )
