#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""


import openstack
import openstack.connection
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.server import Server

from charm_state import OPENSTACK_CLOUDS_YAML_CONFIG_NAME


async def test_openstack_integration(
    model: Model,
    app_no_runner: Application,
    openstack_clouds_yaml: str,
    openstack_connection: openstack.connection.Connection,
):
    """
    arrange: Load the OpenStack clouds.yaml config. Parse project name from the config.
    act: Set the openstack-clouds-yaml config in the charm
    assert: Check the unit log for successful OpenStack connection and that the project is listed.
    """
    await app_no_runner.set_config({OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_clouds_yaml})
    await model.wait_for_idle(apps=[app_no_runner.name])

    servers = openstack_connection.list_servers(detailed=True)
    assert len(servers) == 1, f"Unexpected number of servers: {len(servers)}"
    server: Server = servers[0]
    assert server.image.name == "jammy"
