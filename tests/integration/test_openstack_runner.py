#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

import pytest
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.server import Server
from openstack.connection import Connection as OpenstackConnection

from charm_state import TOKEN_CONFIG_NAME
from tests.integration.helpers.common import ACTIVE, reconcile


async def test_openstack_check_runner(
    app_openstack_runner: Application,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act: Run check-runners action.
    assert: No runners exists.
    """
    unit = app_openstack_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"


async def test_openstack_reconcile_one_runner(
    model: Model,
    app_openstack_runner: Application,
    openstack_connection: OpenstackConnection,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act:
        1. Change number of runners to one and reconcile and run check-runners action.
        2. Change number of runners to zero and run check-runners action.
    assert:
        1. One runner is spawned.
        2. No runners exist and no servers exist on openstack.
    """
    # 1.
    # Waits until one runner is spawned.
    await app_openstack_runner.set_config({"virtual-machines": "1"})
    await reconcile(app=app_openstack_runner, model=model)

    unit = app_openstack_runner.units[0]
    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    # 2.
    await app_openstack_runner.set_config({"virtual-machines": "0"})
    await reconcile(app=app_openstack_runner, model=model)

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    assert len(await openstack_connection.list_servers()) == 0, "Openstack runners not cleaned up"


async def test_openstack_flush_runners(
    model: Model,
    app_openstack_runner: Application,
    openstack_connection: OpenstackConnection,
):
    """
    arrange: An app with runners.
    act: Call flush runners action.
    assert: Runners are flushed and no servers exist on openstack.
    """
    # Waits until one runner is spawned.
    await app_openstack_runner.set_config({"virtual-machines": "1"})
    await reconcile(app=app_openstack_runner, model=model)

    unit = app_openstack_runner.units[0]
    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["delta"]["virtual-machines"] == "1"

    assert len(await openstack_connection.list_servers()) == 0, "Openstack runners not cleaned up"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_token_config_changed(
    model: Model,
    app_openstack_runner: Application,
    openstack_connection: OpenstackConnection,
    token_alt: str,
) -> None:
    """
    arrange: A working application with one runner.
    act: Change the token configuration.
    assert: New runner is spawned.
    """
    # Waits until one runner is spawned.
    await app_openstack_runner.set_config({"virtual-machines": "1"})
    await reconcile(app=app_openstack_runner, model=model)
    servers: list[Server] = openstack_connection.list_servers()
    assert len(servers) == 1, f"Invalid number of servers found, expected 1, got {len(servers)}"
    server_id = servers[0].id

    await app_openstack_runner.set_config({TOKEN_CONFIG_NAME: token_alt})
    await model.wait_for_idle(status=ACTIVE, timeout=30 * 60)

    servers = openstack_connection.list_servers()
    assert len(servers) == 1, f"Invalid number of servers found, expected 1, got {len(servers)}"
    assert (
        server_id != servers[0].id
    ), f"Expected new runner spawned, same server id found {server_id}"
