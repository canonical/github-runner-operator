#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for charm upgrades."""

import functools
import pathlib

import jubilant
import pytest
from juju.application import Application
from juju.client import client
from juju.model import Model

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    OPENSTACK_NETWORK_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
)
from tests.integration.conftest import GitHubConfig, OpenStackConfig
from tests.integration.helpers.common import (
    deploy_github_runner_charm,
    is_upgrade_charm_event_emitted,
    wait_for,
)

pytestmark = pytest.mark.openstack


@pytest.mark.asyncio
async def test_charm_upgrade(
    juju: jubilant.Juju,
    model: Model,
    charm_file: str,
    app_name: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    tmp_path: pathlib.Path,
    image_builder: Application,
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
            "--series",
            "jammy",
            "--filepath",
            str(latest_edge_path),
            "--no-progress",
            include_model=False,
        )
    except jubilant.CLIError as exc:
        pytest.fail(f"failed to download charm, {exc}")

    # deploy latest edge version of the charm
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=str(latest_edge_path),
        app_name=app_name,
        path=github_config.path,
        token=github_config.token,
        http_proxy=openstack_config.http_proxy,
        https_proxy=openstack_config.https_proxy,
        no_proxy=openstack_config.no_proxy,
        reconcile_interval=5,
        # override default virtual_machines=0 config.
        config={
            OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_config.clouds_yaml_contents,
            OPENSTACK_NETWORK_CONFIG_NAME: openstack_config.network_name,
            OPENSTACK_FLAVOR_CONFIG_NAME: openstack_config.flavor_name,
            USE_APROXY_CONFIG_NAME: "true",
            VIRTUAL_MACHINES_CONFIG_NAME: 0,
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: 1,
        },
        wait_idle=False,
    )
    await model.integrate(f"{image_builder.name}", f"{application.name}:image")
    await model.wait_for_idle(
        apps=[application.name, image_builder.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=25 * 60,
        check_freq=30,
    )
    origin = client.CharmOrigin(
        source="charm-hub",
        track="22.04",
        risk="latest/edge",
        branch="deadbeef",
        hash_="hash",
        id_="id",
        revision=0,  # arbitrary number
        base=client.Base("22.04", "ubuntu"),
    )

    # upgrade the charm with current local charm
    await application.local_refresh(
        path=charm_file,
        charm_origin=origin,
        force=False,
        force_series=False,
        force_units=False,
        resources=None,
    )
    unit = application.units[0]
    await wait_for(
        functools.partial(is_upgrade_charm_event_emitted, unit), timeout=360, check_interval=60
    )
    await model.wait_for_idle(
        apps=[application.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=20 * 60,
        check_freq=30,
    )
