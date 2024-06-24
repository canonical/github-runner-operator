# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

The forked repo is configured to fail the repo-policy-compliance check.
"""

from datetime import datetime, timezone

import pytest
import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import PATH_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    InstanceHelper,
    dispatch_workflow,
    reconcile,
)
from tests.integration.helpers.lxd import ensure_charm_has_runner, get_runner_names
from tests.integration.helpers.openstack import (
    OpenStackInstanceHelper,
    setup_runner_with_repo_policy,
)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dispatch_workflow_failure(
    app_with_forked_repo: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
    instance_helper: InstanceHelper,
    token: str,
    https_proxy: str,
) -> None:
    """
    arrange: \
        1. A forked repository. \
        2. A working application using repo-policy checks with one runner on the forked repository.
    act: Trigger a workflow dispatch that fails the repo policy check on a branch
     in the forked repository.
    assert: The workflow that was dispatched failed and the reason is logged.
    """
    start_time = datetime.now(timezone.utc)

    if isinstance(instance_helper, OpenStackInstanceHelper):
        await setup_runner_with_repo_policy(
            app=app_with_forked_repo,
            openstack_connection=instance_helper.openstack_connection,
            token=token,
            https_proxy=https_proxy,
        )

    await instance_helper.ensure_charm_has_runner(app_with_forked_repo)

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME
    )

    await dispatch_workflow(
        app=app_with_forked_repo,
        workflow_id_or_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="failure",
    )

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore, all runs after this test start should pass the conditions.
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        if start_time > run.created_at:
            continue

        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if f"Job is about to start running on the runner: {app_with_forked_repo.name}-" in logs:
            assert run.jobs()[0].conclusion == "failure"
            assert (
                "Stopping execution of jobs due to repository setup is not compliant with policies"
                in logs
            )
            assert "Endpoint designed for testing that always fails" in logs
            assert "Should not echo if pre-job script failed" not in logs


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_path_config_change(
    model: Model,
    app_with_forked_repo: Application,
    github_repository: Repository,
    path: str,
) -> None:
    """
    arrange: A working application with one runner in a forked repository.
    act: Change the path configuration to the main repository and reconcile runners.
    assert: No runners connected to the forked repository and one runner in the main repository.
    """
    unit = app_with_forked_repo.units[0]
    await ensure_charm_has_runner(app=app_with_forked_repo, model=model)

    await app_with_forked_repo.set_config({PATH_CONFIG_NAME: path})

    await reconcile(app=app_with_forked_repo, model=model)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
