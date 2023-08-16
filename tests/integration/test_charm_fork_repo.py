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
from github import Consts, Github
from github.Branch import Branch
from github.GithubException import GithubException
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import assert_num_of_runners, get_runner_names, on_juju_2
from tests.status_name import ACTIVE_STATUS_NAME

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"


@pytest.fixture(scope="module")
def github_client(token: str) -> Github:
    """Returns the github client."""
    return Github(token)


@pytest.fixture(scope="module")
def github_repository(github_client: Github, path: str) -> Repository:
    """Returns client to the Github repository."""
    return github_client.get_repo(path)


@pytest.fixture(scope="module")
def forked_github_repository(
    github_repository: Repository,
) -> Iterator[Repository]:
    """Create a fork for a GitHub repository."""
    name = f"{github_repository.name}/{secrets.token_hex(8)}"
    if on_juju_2():
        name += "-juju2"
    forked_repository = github_repository.create_fork(name=name)

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

    forked_repository.delete()


@pytest.fixture(scope="module")
def forked_github_branch(forked_github_repository: Repository) -> Iterator[Branch]:
    """Create a new forked branch for testing."""
    branch_name = f"test/{secrets.token_hex(8)}"

    main_branch = forked_github_repository.get_branch(forked_github_repository.default_branch)
    branch_ref = forked_github_repository.create_git_ref(
        ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha
    )
    branch = forked_github_repository.get_branch(branch_name)

    yield branch

    branch_ref.delete()


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
    unit = app_no_runner.units[0]

    await app_no_runner.set_config(
        {"virtual-machines": "1", "path": forked_github_repository.full_name}
    )
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    # Wait until there is one runner.
    await assert_num_of_runners(unit, 1)

    yield app_no_runner


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
    assert: The workflow that was dispatched failed.
    """
    unit = app_with_unsigned_commit_repo.units[0]
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    runner_to_be_used = runners[0]

    workflow = forked_github_repository.get_workflow(id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME)

    assert not list(workflow.get_runs()), "Existing workflow runs in created fork repo"

    workflow.create_dispatch(
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

    # The only job in the workflow is job that `echo` the runner name. If it fails then it should
    # be the pre-run job that failed.
    run = workflow.get_runs()[0]
    assert run.jobs()[0].conclusion == "failure"


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
