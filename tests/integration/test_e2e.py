#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.helpers.common import (
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    dispatch_workflow,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model,
    basic_app: Application,
    instance_helper: OpenStackInstanceHelper,
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure the charm has one runner before starting a test.
    """
    await instance_helper.ensure_charm_has_runner(basic_app)
    yield basic_app


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_e2e_workflow(
    model: Model,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act: Run e2e test workflow.
    assert: No exception thrown.
    """
    await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
        dispatch_input={"runner-tag": app.name},
    )
