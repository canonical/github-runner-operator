# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

The forked repo is configured to fail the repo-policy-compliance check.
"""

import secrets
from time import sleep
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
import requests
from github import Consts
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    create_runner,
    get_runner_names,
    reconcile,
)


@pytest.fixture(scope="module")
def branch_with_unsigned_commit(
    forked_github_branch: Branch, forked_github_repository: Repository
):
    """Create branch that would fail the branch protection check.

    Makes the branch the default branch for the repository and makes the latest commit unsigned.
    """
    # Make an unsigned commit
    forked_github_repository.create_file(
        "test.txt", "testing", "some content", branch=forked_github_branch.name
    )

    # Change default branch so that the commit is ignored by the check for unique commits being
    # signed
    forked_github_repository.edit(default_branch=forked_github_branch.name)

    # forked_github_branch.edit_protection seems to be broken as of version 1.59 of PyGithub.
    # Without passing the users_bypass_pull_request_allowances the API returns a 422 indicating
    # that None is not a valid value for bypass pull request allowances, with it there is a 422 for
    # forks indicating that users and teams allowances can only be set on organisation
    # repositories.
    post_parameters = {
        "required_status_checks": None,
        "enforce_admins": None,
        "required_pull_request_reviews": {"dismiss_stale_reviews": False},
        "restrictions": None,
    }
    # pylint: disable=protected-access
    forked_github_branch._requester.requestJsonAndCheck(  # type: ignore
        "PUT",
        forked_github_branch.protection_url,
        headers={"Accept": Consts.mediaTypeRequireMultipleApprovingReviews},
        input=post_parameters,
    )
    # pylint: enable=protected-access
    forked_github_branch.add_required_signatures()

    yield forked_github_branch

    forked_github_branch.remove_protection()


@pytest_asyncio.fixture(scope="module")
async def app_with_unsigned_commit_repo(
    model: Model, app_no_runner: Application, forked_github_repository: Repository
) -> AsyncIterator[Application]:
    """Application with a single runner on a repo with unsigned commit.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    app = app_no_runner  # alias for readability as the app will have a runner during the test

    await app.set_config({"path": forked_github_repository.full_name})
    await create_runner(app=app, model=model)

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
    unit = app_with_unsigned_commit_repo.units[0]
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    runner_to_be_used = runners[0]

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
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

    for run in workflow.get_runs():
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
            assert "commit the job is running on is not signed" in logs
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
    arrange: A working application with one runner in a forked repoistory.
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
