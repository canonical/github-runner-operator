# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with juju-storage as disk."""

import pytest
from juju.application import Application
from juju.model import Model

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import reconcile
from tests.integration.helpers.lxd import wait_till_num_of_runners


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_spawn_one_runner(model: Model, app_juju_storage: Application) -> None:
    """
    arrange: A working application with no runners and juju storage setup.
    act: Spawn one runner.
    assert: One runner should exist.
    """
    await app_juju_storage.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await reconcile(app=app_juju_storage, model=model)

    await wait_till_num_of_runners(unit=app_juju_storage.units[0], num=1)
