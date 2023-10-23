# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

The forked repo is configured to fail the repo-policy-compliance check.
"""

import secrets
from datetime import datetime, timezone
from time import sleep
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
import requests
from github import Consts
from github.Branch import Branch
from github.GithubException import GithubException
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.conftest import DISPATCH_TEST_WORKFLOW_FILENAME
from tests.integration.helpers import create_runner, get_runner_names
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.fixture(scope="module")
def github_repository(
    github_repository: Repository,
) -> Iterator[Repository]:
    """Create a fork for a GitHub repository."""
    forked_repository = github_repository.create_fork(name=f"test-{github_repository.name}")

    # Wait for repo to be ready
    for _ in range(10):
        try:
            sleep(10)
            forked_repository.get_branches()
            break
        except GithubException:
            pass
    else:
        assert False, "timed out whilst waiting for repository creation"

    yield forked_repository

    # Parallel runs of this test module is allowed. Therefore, the forked repo is not removed.


@pytest.fixture(scope="module")
def forked_github_branch(github_repository: Repository) -> Iterator[Branch]:
    """Create a new forked branch for testing."""
    branch_name = f"test/{secrets.token_hex(4)}"

    main_branch = github_repository.get_branch(github_repository.default_branch)
    branch_ref = github_repository.create_git_ref(
        ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha
    )

    for _ in range(10):
        try:
            branch = github_repository.get_branch(branch_name)
            break
        except GithubException as err:
            if err.status == 404:
                sleep(5)
                continue
            raise
    else:
        assert (
            False
        ), "Failed to get created branch in fork repo, the issue with GitHub or network."

    yield branch

    branch_ref.delete()


@pytest.fixture(scope="module")
def branch_with_unsigned_commit(
    forked_github_branch: Branch, github_repository: Repository
):
    """Create branch that would fail the branch protection check.

    Makes the branch the default branch for the repository and makes the latest commit unsigned.
    """
    # Make an unsigned commit
    github_repository.create_file(
        "test.txt", "testing", "some content", branch=forked_github_branch.name
    )

    # Change default branch so that the commit is ignored by the check for unique commits being
    # signed
    github_repository.edit(default_branch=forked_github_branch.name)

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
    github_repository: Repository,
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

    workflow = github_repository.get_workflow(
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

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore find the last few workflow runs, and ensure:
    # 1. The last run check should start before this test.
    # 2. All runs after this test start should pass the conditions.
    assert start_time > workflow.get_runs()[9].created_at
    for run in workflow.get_runs()[:10]:
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

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
