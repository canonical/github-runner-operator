#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""


import openstack
import openstack.connection
from github.Branch import Branch
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.server import Server

from tests.integration.helpers import DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME, dispatch_workflow


async def test_openstack_integration(
    model: Model,
    app_openstack_runner: Application,
    openstack_connection: openstack.connection.Connection,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: given a runner with openstack cloud configured.
    act:
        1. when the e2e_test_run workflow is created.
        2. when the servers are listed.
    assert:
        1. the workflow run completes successfully.
        2. a server with image name jammy is created.
    """
    await model.wait_for_idle(apps=[app_openstack_runner.name], status="blocked", timeout=40 * 60)

    # 1. when the e2e_test_run workflow is created.
    workflow = await dispatch_workflow(
        app=app_openstack_runner,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    )
    # 1. the workflow run completes successfully.
    workflow_run: WorkflowRun = workflow.get_runs()[0]
    assert workflow_run.status == "success"

    # 2. when the servers are listed.
    servers = openstack_connection.list_servers(detailed=True)
    assert len(servers) == 1, f"Unexpected number of servers: {len(servers)}"
    server: Server = servers[0]
    # 2. a server with image name jammy is created.
    assert server.image.name == "jammy"
