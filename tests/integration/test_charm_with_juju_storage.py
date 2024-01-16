# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with juju-storage as disk."""

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import reconcile, wait_till_num_of_runners


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_spawn_one_runner(model: Model, app_juju_storage: Application) -> None:
    """
    arrange: A working application with no runners and juju storage setup.
    act: Spawn one runner.
    assert: One runner should exist.
    """
    await app_juju_storage.set_config({"virtual-machines": "1"})
    await reconcile(app=app_juju_storage, model=model)

    await wait_till_num_of_runners(unit=app_juju_storage.units[0], num=1)
