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

from tests.integration.helpers.common import (
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    InstanceHelper,
    dispatch_workflow,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, setup_repo_policy
from tests.status_name import ACTIVE


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dispatch_workflow_failure(
    model: Model,
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
        await setup_repo_policy(
            app=app_with_forked_repo,
            openstack_connection=instance_helper.openstack_connection,
            token=token,
            https_proxy=https_proxy,
        )
    else:
        grafana_agent = await model.deploy(
            "grafana-agent",
            application_name=f"grafana-agent-{app_with_forked_repo.name}",
            channel="latest/edge",
        )
        await model.relate(
            f"{app_with_forked_repo.name}:cos-agent", f"{grafana_agent.name}:cos-agent"
        )
        await model.wait_for_idle(apps=[app_with_forked_repo.name], status=ACTIVE)
        await model.wait_for_idle(apps=[grafana_agent.name])
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
