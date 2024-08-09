# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test for OpenstackCloud class integration with OpenStack."""

from secrets import token_hex

import pytest
import pytest_asyncio
import yaml
from openstack.connection import Connection as OpenstackConnection

from openstack_cloud.openstack_cloud import OpenstackCloud


@pytest_asyncio.fixture(scope="function", name="base_openstack_cloud")
async def base_openstack_cloud_fixture(private_endpoint_clouds_yaml: str) -> OpenstackCloud:
    """Setup a OpenstackCloud object with connection to openstack."""
    clouds_yaml = yaml.safe_load(private_endpoint_clouds_yaml)
    return OpenstackCloud(clouds_yaml, "testcloud", f"test-{token_hex(4)}")


@pytest_asyncio.fixture(scope="function", name="openstack_cloud")
async def openstack_cloud_fixture(base_openstack_cloud: OpenstackCloud) -> OpenstackCloud:
    """Ensures the OpenstackCloud object has no openstack servers."""
    instances = base_openstack_cloud.get_instances()
    for instance in instances:
        base_openstack_cloud.delete_instance(instance_id=instance.instance_id)
    return base_openstack_cloud


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_get_no_instances(base_openstack_cloud: OpenstackCloud) -> None:
    """
    arrange: No instance on OpenStack.
    act: Get instances on OpenStack.
    assert: An empty list returned.

    Uses base_openstack_cloud as openstack_cloud_fixture relies on this test.
    """
    instances = base_openstack_cloud.get_instances()
    assert not instances


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_launch_instance_and_delete(
    base_openstack_cloud: OpenstackCloud,
    openstack_connection: OpenstackConnection,
    openstack_test_image: str,
    openstack_test_flavor: str,
    network_name: str,
) -> None:
    """
    arrange: No instance on OpenStack.
    act:
        1. Create an openstack instance.
        2. Delete openstack instance.
    assert:
        1. Instance returned.
        2. No instance exists.

    Uses base_openstack_cloud as openstack_cloud_fixture relies on this test.
    """
    instances = base_openstack_cloud.get_instances()
    assert not instances, "Test arrange failure: found existing openstack instance."

    instance_name = f"{token_hex(2)}"

    # 1.
    instance = base_openstack_cloud.launch_instance(
        instance_id=instance_name,
        image=openstack_test_image,
        flavor=openstack_test_flavor,
        network=network_name,
        userdata="",
    )

    assert instance is not None
    assert instance.instance_id is not None
    assert instance.server_name is not None
    assert instance.id is not None

    servers = openstack_connection.list_servers()
    for server in servers:
        if instance_name in server.name:
            break
    else:
        assert False, f"OpenStack server with {instance_name} in the name not found"

    # 2.
    base_openstack_cloud.delete_instance(instance_id=instance_name)
    instances = base_openstack_cloud.get_instances()
    assert not instances, "Test failure: openstack instance should be deleted."


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_instance_ssh_connection(
    openstack_cloud: OpenstackCloud,
    openstack_test_image: str,
    openstack_test_flavor: str,
    network_name: str,
) -> None:
    """
    arrange: One instance on OpenStack.
    act: Get SSH connection of instance and execute command.
    assert: Test SSH command executed successfully.

    This tests whether the network rules (security group) are in place.
    """
    rand_chars = f"{token_hex(10)}"
    instance_name = f"{token_hex(2)}"
    instance = openstack_cloud.launch_instance(
        instance_id=instance_name,
        image=openstack_test_image,
        flavor=openstack_test_flavor,
        network=network_name,
        userdata="",
    )

    ssh_conn = openstack_cloud.get_ssh_connection(instance)
    result = ssh_conn.run(f"echo {rand_chars}")

    assert result.ok
    assert rand_chars in result.stdout
