#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

import openstack.connection
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.server import Server

from charm_state import BASE_IMAGE_CONFIG_NAME
from tests.integration.helpers import (
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    dispatch_workflow,
    wait_for,
)


async def test_noble_base_image(
    model: Model,
    app_openstack_runner: Application,
    openstack_connection: openstack.connection.Connection,
    github_repository: Repository,
    test_github_branch: Branch,
) -> None:
    """
    arrange: A runner with noble as base image.
    act: Dispatch a workflow.
    assert: A server with noble image base is created and the workflow runs successfully.
    """
    await app_openstack_runner.set_config(
        {
            BASE_IMAGE_CONFIG_NAME: "noble",
        }
    )
    await model.wait_for_idle(apps=[app_openstack_runner.name], status="blocked", timeout=50 * 60)

    #  Server with noble base image is created
    servers = openstack_connection.list_servers(detailed=True)
    assert len(servers) == 1, f"Unexpected number of servers: {len(servers)}"
    server: Server = servers[0]
    assert "noble" in server.image.name

    # Workflow completes successfully
    workflow = await dispatch_workflow(
        app=app_openstack_runner,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
        dispatch_input={"runner-tag": app_openstack_runner.name},
    )
    await wait_for(lambda: workflow.get_runs()[0].status == "completed")
