# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

The forked repo is configured to fail the repo-policy-compliance check.
"""

from datetime import datetime, timezone
from time import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_names,
    reconcile,
)


@pytest_asyncio.fixture(scope="module")
async def app_with_forked_repo(
    model: Model, app_no_runner: Application, forked_github_repository: Repository
) -> AsyncIterator[Application]:
    """Application with a single runner on a forked repo.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    app = app_no_runner  # alias for readability as the app will have a runner during the test

    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    yield app


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dispatch_workflow_failure(
    app_with_unsigned_commit_repo: Application,
    forked_github_repository: Repository,
    branch_with_unsigned_commit: Branch,
) -> None:
    """
    arrange:
        1. A forked repository with unsigned commit in default branch.
        2. A working application with one runner on the forked repository.
    act: Trigger a workflow dispatch on a branch in the forked repository.
    assert: The workflow that was dispatched failed and the reason is logged.
    """
    start_time = datetime.now(timezone.utc)

    unit = app_with_unsigned_commit_repo.units[0]
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    runner_to_be_used = runners[0]

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME
    )

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(
        branch_with_unsigned_commit, {"runner": app_with_unsigned_commit_repo.name}
    )

    # Wait until the runner is used up.
    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner_to_be_used not in runners:
            break
        sleep(30)
    else:
        assert False, "Timeout while waiting for workflow to complete"

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore, all runs after this test start should pass the conditions.
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        if start_time > run.created_at:
            continue

        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if (
            f"Job is about to start running on the runner: {app_with_unsigned_commit_repo.name}-"
            in logs
        ):
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
    app_with_unsigned_commit_repo: Application,
    github_repository: Repository,
    path: str,
) -> None:
    """
    arrange: A working application with one runner in a forked repository.
    act: Change the path configuration to the main repository and reconcile runners.
    assert: No runners connected to the forked repository and one runner in the main repository.
    """
    unit = app_with_unsigned_commit_repo.units[0]

    await app_with_unsigned_commit_repo.set_config({"path": path})

    await reconcile(app=app_with_unsigned_commit_repo, model=model)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
