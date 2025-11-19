# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

The forked repo is configured to fail the repo-policy-compliance check.
"""

import secrets
from datetime import datetime, timezone
from time import sleep
from typing import Iterator

import pytest
import pytest_asyncio
import requests
from github import Github
from github.Branch import Branch
from github.GithubException import GithubException
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import ALLOW_EXTERNAL_CONTRIBUTOR_CONFIG_NAME, PATH_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, setup_repo_policy


@pytest_asyncio.fixture(scope="module")
async def app_with_forked_repo(
    model: Model, basic_app: Application, forked_github_repository: Repository
) -> Application:
    """Application with no runner on a forked repo.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    await basic_app.set_config({PATH_CONFIG_NAME: forked_github_repository.full_name})

    return basic_app


@pytest.fixture(scope="module")
def trusted_forked_github_repository(
    github_repository: Repository,
    github_client: Github,
    token_alt: str,
) -> Iterator[Repository]:
    """Create a fork from an alternate user account and add that user as collaborator.

    This fixture creates a fork using token_alt (different GitHub user) and then
    adds that user as a collaborator with push permissions to the original repository.
    This simulates a trusted fork scenario where the fork owner is a COLLABORATOR.

    Note: token_alt must represent a different GitHub user account than token.
    """
    # Create GitHub client with alternate token
    alt_github_client = Github(token_alt)
    alt_user = alt_github_client.get_user()
    primary_user = github_client.get_user()

    # Verify tokens represent different users
    assert (
        alt_user.login != primary_user.login
    ), f"token_alt must be from a different user. Both tokens have user: {alt_user.login}"

    # Get the repository using alternate token to create fork from that account
    alt_repo_ref = alt_github_client.get_repo(github_repository.full_name)
    trusted_fork = alt_repo_ref.create_fork(name=f"test-trusted-{github_repository.name}")

    # Wait for fork to be ready
    for _ in range(10):
        try:
            sleep(10)
            trusted_fork.get_branches()
            break
        except GithubException:
            pass
    else:
        assert False, "timed out whilst waiting for trusted fork creation"

    # Add alternate user as collaborator to original repository
    github_repository.add_to_collaborators(alt_user.login, permission="push")

    # Wait for collaborator permissions to propagate
    for _ in range(10):
        try:
            if github_repository.has_in_collaborators(alt_user.login):
                break
            sleep(5)
        except GithubException:
            sleep(5)
    else:
        assert False, "timed out whilst waiting for collaborator permissions to propagate"

    yield trusted_fork

    # Cleanup: Remove collaborator
    try:
        github_repository.remove_from_collaborators(alt_user.login)
    except GithubException:
        pass  # Best effort cleanup

    # Note: Fork is not deleted to support parallel test runs


@pytest.fixture(scope="module")
def trusted_forked_github_branch(
    github_repository: Repository, trusted_forked_github_repository: Repository
) -> Iterator[Branch]:
    """Create a new branch in the trusted forked repository for testing."""
    branch_name = f"test/{secrets.token_hex(4)}"

    main_branch = trusted_forked_github_repository.get_branch(github_repository.default_branch)
    branch_ref = trusted_forked_github_repository.create_git_ref(
        ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha
    )

    for _ in range(10):
        try:
            branch = trusted_forked_github_repository.get_branch(branch_name)
            break
        except GithubException as err:
            if err.status == 404:
                sleep(5)
                continue
            raise
    else:
        assert (
            False
        ), "Failed to get created branch in trusted fork repo, issue with GitHub or network."

    yield branch

    branch_ref.delete()


@pytest_asyncio.fixture(scope="module")
async def app_with_trusted_forked_repo(
    model: Model, basic_app: Application, trusted_forked_github_repository: Repository
) -> Application:
    """Application with no runner on a trusted forked repo.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    await basic_app.set_config({PATH_CONFIG_NAME: trusted_forked_github_repository.full_name})

    return basic_app


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dispatch_workflow_failure(
    model: Model,
    app_with_forked_repo: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
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

    await setup_repo_policy(
        app=app_with_forked_repo,
        openstack_connection=instance_helper.openstack_connection,
        token=token,
        https_proxy=https_proxy,
    )

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


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_untrusted_fork_owner_workflow_blocked(
    model: Model,
    app_with_forked_repo: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A forked repository where the owner is NOT OWNER/MEMBER/COLLABORATOR \
        and allow-external-contributor is set to False.
    act: Trigger a workflow dispatch from the untrusted forked repository.
    assert: The workflow execution fails and insufficient authorization is logged.
    """
    start_time = datetime.now(timezone.utc)

    # Set allow-external-contributor to False to block untrusted forks
    await app_with_forked_repo.set_config({ALLOW_EXTERNAL_CONTRIBUTOR_CONFIG_NAME: "false"})
    await instance_helper.ensure_charm_has_runner(app_with_forked_repo)

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
    )

    await dispatch_workflow(
        app=app_with_forked_repo,
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
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
            assert "Insufficient user authorization (author_association)" in logs
            assert "Only OWNER, MEMBER, or COLLABORATOR may run workflows" in logs


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_trusted_fork_owner_workflow_succeeds(
    model: Model,
    app_with_trusted_forked_repo: Application,
    trusted_forked_github_repository: Repository,
    trusted_forked_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A forked repository where the owner IS a COLLABORATOR \
        and allow-external-contributor is set to False.
    act: Trigger a workflow dispatch from the trusted forked repository.
    assert: The workflow completes successfully and contributor check passes.
    """
    start_time = datetime.now(timezone.utc)

    # Set allow-external-contributor to False, but this should still succeed
    # because the fork owner is a COLLABORATOR
    await app_with_trusted_forked_repo.set_config(
        {ALLOW_EXTERNAL_CONTRIBUTOR_CONFIG_NAME: "false"}
    )
    await instance_helper.ensure_charm_has_runner(app_with_trusted_forked_repo)

    workflow = trusted_forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
    )

    await dispatch_workflow(
        app=app_with_trusted_forked_repo,
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        branch=trusted_forked_github_branch,
        github_repository=trusted_forked_github_repository,
        conclusion="success",
    )

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore, all runs after this test start should pass the conditions.
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        if start_time > run.created_at:
            continue

        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if (
            f"Job is about to start running on the runner: {app_with_trusted_forked_repo.name}-"
            in logs
        ):
            assert run.jobs()[0].conclusion == "success"
            assert "The contributor check has passed, proceeding to execute jobs" in logs
            assert "Insufficient user authorization (author_association)" not in logs
