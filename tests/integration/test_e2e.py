#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""End-to-end integration test."""

from typing import Iterator

import pytest
from github.Branch import Branch
from github.Repository import Repository

from tests.integration.helpers.common import (
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    dispatch_workflow,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest.fixture(scope="function", name="app")
def app_fixture(
    basic_app: str,
    instance_helper: OpenStackInstanceHelper,
) -> Iterator[str]:
    """Setup and teardown the charm after each test.

    Ensure the charm has one runner before starting a test.
    """
    instance_helper.ensure_charm_has_runner(basic_app)
    yield basic_app


@pytest.mark.openstack
@pytest.mark.abort_on_fail
def test_e2e_workflow(
    app: str,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: An app connected to an OpenStack cloud with no runners.
    act: Run e2e test workflow.
    assert: No exception thrown.
    """
    dispatch_workflow(
        app_name=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
        dispatch_input={"runner-tag": app},
    )
