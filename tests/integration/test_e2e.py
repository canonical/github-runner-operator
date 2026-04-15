#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""End-to-end integration test.

Uses GitHub App authentication when credentials are provided, falling back to PAT.
"""

import logging
from typing import Iterator

import pytest
from github.Branch import Branch
from github.Repository import Repository

from tests.integration.conftest import GitHubConfig
from tests.integration.helpers.common import (
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    dispatch_workflow,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest.fixture(scope="module")
def github_config(pytestconfig: pytest.Config, github_config: GitHubConfig) -> GitHubConfig:
    """Override github_config to prefer GitHub App auth when credentials are available."""
    app_client_id = pytestconfig.getoption("--github-app-client-id") or None
    installation_id_raw = pytestconfig.getoption("--github-app-installation-id") or None
    private_key = pytestconfig.getoption("--github-app-private-key") or None

    if not all((app_client_id, installation_id_raw, private_key)):
        logging.info("Using PAT authentication for e2e test")
        return github_config

    logging.info("Using GitHub App authentication for e2e test")
    return GitHubConfig(
        token=github_config.token,
        path=github_config.path,
        app_client_id=app_client_id,
        installation_id=int(installation_id_raw),  # type: ignore[arg-type]
        private_key=private_key,
    )


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
