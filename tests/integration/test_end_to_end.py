#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import pytest
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.server import Server
from openstack.connection import Connection as OpenstackConnection

from charm_state import TOKEN_CONFIG_NAME
from tests.integration.helpers.common import (
    ACTIVE,
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    reconcile,
)
from tests.integration.helpers.openstack import setup_repo_policy


async def test_end_to_end(
    model: Model,
    app_openstack_runner: Application,
    github_repository: Repository,
    test_github_branch: Branch,
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

    await dispatch_workflow(
        app=app_openstack_runner,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    )