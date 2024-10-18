#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for charm upgrades."""

import functools
import pathlib

import pytest
from juju.client import client
from juju.model import Model
from pytest_operator.plugin import OpsTest

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import (
    deploy_github_runner_charm,
    inject_lxd_profile,
    is_upgrade_charm_event_emitted,
    wait_for,
)


@pytest.mark.asyncio
async def test_charm_upgrade(
    model: Model,
    ops_test: OpsTest,
    charm_file: str,
    loop_device: str | None,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
    tmp_path: pathlib.Path,
):
    """
    arrange: given latest stable version of the charm (current 161).
    act: charm upgrade is called.
    assert: the charm is upgraded successfully.
    """
    latest_stable_path = tmp_path / "github-runner.charm"
    latest_stable_revision = 256  # update this value every release to stable.
    # download the charm and inject lxd profile for testing
    retcode, stdout, stderr = await ops_test.juju(
        "download",
        "github-runner",
        # do not specify revision
        # --revision cannot be specified together with --arch, --base, --channel
        "--channel",
        "latest/stable",
        "--series",
        "jammy",
        "--filepath",
        str(latest_stable_path),
        "--no-progress",
    )
    assert retcode == 0, f"failed to download charm, {stdout} {stderr}"
    inject_lxd_profile(pathlib.Path(latest_stable_path), loop_device=loop_device)

    # deploy latest stable version of the charm
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=str(latest_stable_path),
        app_name=app_name,
        path=path,
        token=token,
        runner_storage="juju-storage",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=5,
        # override default virtual_machines=0 config.
        config={VIRTUAL_MACHINES_CONFIG_NAME: 1},
    )
    await model.wait_for_idle(
        apps=[application.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=180 * 60,
        check_freq=30,
    )
    origin = client.CharmOrigin(
        source="charm-hub",
        track="22.04",
        risk="latest/stable",
        branch="deadbeef",
        hash_="hash",
        id_="id",
        revision=latest_stable_revision,
        base=client.Base("22.04", "ubuntu"),
    )

    # upgrade the charm with current local charm
    await application.local_refresh(path=charm_file, charm_origin=origin)
    unit = application.units[0]
    await wait_for(
        functools.partial(is_upgrade_charm_event_emitted, unit), timeout=360, check_interval=60
    )
    await model.wait_for_idle(
        apps=[application.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=180 * 60,
        check_freq=30,
    )
