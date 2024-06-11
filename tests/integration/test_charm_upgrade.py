#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for charm upgrades."""

import pytest
from juju.model import Model

from tests.integration.helpers import deploy_github_runner_charm


@pytest.mark.asyncio
async def test_charm_upgrade(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
):
    """
    arrange: given latest stable version of the charm.
    act: charm upgrade is called.
    assert: the charm is upgraded successfully.
    """
    # deploy latest stable version of the charm
    application = await deploy_github_runner_charm(
        model=model,
        charm_file="github-runner",
        app_name=app_name,
        path=path,
        token=token,
        runner_storage="juju-storage",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=5,
        constraints={
            "root-disk": 20 * 1024,
            "cores": 4,
            "mem": 16 * 1024,
            "virt-type": "virtual-machine",
        },
        deploy_kwargs={
            "channel": "latest/stable",
            "revision": 161,
        },
    )
    await model.wait_for_idle(
        apps=[application.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=180 * 60,
        check_freq=30,
    )

    # upgrade the charm with current local charm
    await application.local_refresh(path=charm_file)
    await model.wait_for_idle(
        apps=[application.name],
        raise_on_error=False,
        wait_for_active=True,
        timeout=180 * 60,
        check_freq=30,
    )
