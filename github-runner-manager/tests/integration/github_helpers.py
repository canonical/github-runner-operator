# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper functions for GitHub integration testing."""

import logging
from datetime import datetime, timezone
from time import sleep, time

import requests
from github.Branch import Branch
from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun

logger = logging.getLogger(__name__)


def create_fork_and_pr(
    upstream_repository: Repository,
    forked_github_repository: Repository,
    test_id: str,
) -> PullRequest:
    """Create a PR from a forked repository.

    Args:
        upstream_repository: The original repository.
        forked_github_repository: The forked repository.
        test_id: Unique test identifier.

    Returns:
        The created pull request.
    """
    # Create a unique branch in the fork
    branch_name = f"test/{test_id}"
    main_branch = forked_github_repository.get_branch(upstream_repository.default_branch)
    forked_github_repository.create_git_ref(
        ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha
    )

    # Create a test file to ensure there's a change
    test_file_path = f"test-{test_id}.txt"
    forked_github_repository.create_file(
        path=test_file_path,
        message=f"Test change from fork {test_id}",
        content=f"Test content {test_id}",
        branch=branch_name,
    )

    # Create PR from fork to original repository
    pr = upstream_repository.create_pull(
        title=f"Test PR from fork {test_id}",
        body=(
            f"This is a test PR from a forked repository for testing "
            f"external contributor security. Test ID: {test_id}"
        ),
        base=upstream_repository.default_branch,
        head=f"{forked_github_repository.owner.login}:{branch_name}",
    )

    return pr


def wait_for_workflow_completion(run: WorkflowRun, timeout: int = 600) -> bool:
    """Wait for a workflow run to complete.

    Args:
        run: The workflow run to wait for.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if workflow completed, False if timeout.
    """
    start_time = time()
    while time() - start_time < timeout:
        run.update()
        if run.status == "completed":
            return True
        sleep(10)
    return False


def get_job_logs(run: WorkflowRun) -> str:
    """Get the logs from a workflow run's first job.

    Args:
        run: The workflow run.

    Returns:
        The job logs as a string.
    """
    jobs = run.jobs()
    if jobs.totalCount == 0:
        return ""

    logs = ""
    for job in jobs:
        logs_url = job.logs_url()
        response = requests.get(logs_url)
        logs += response.content.decode("utf-8")

    return logs


def close_pull_request(pr: PullRequest) -> None:
    """Close a pull request (best effort).

    Args:
        pr: The pull request to close.
    """
    try:
        pr.edit(state="closed")
    except GithubException:
        pass  # Best effort cleanup


def get_pr_workflow_runs(
    repository: Repository,
    pr: PullRequest,
    workflow_name: str,
    timeout: int = 120,
) -> list[WorkflowRun]:
    """Get workflow runs triggered by a pull request.

    Args:
        repository: The repository containing the workflow.
        pr: The pull request that triggered the workflow.
        workflow_name: The name of the workflow to look for.
        timeout: Maximum time to wait for workflow runs to appear in seconds.

    Returns:
        List of workflow runs matching the criteria, sorted by created_at descending
        (most recent first).
    """
    start_time = time()
    while time() - start_time < timeout:
        # Get all runs for this PR
        all_runs = repository.get_workflow_runs(
            event="pull_request",
            head_sha=pr.head.sha,
        )

        # Filter by workflow name
        matching_runs = [run for run in all_runs if run.name == workflow_name]

        if matching_runs:
            # Sort by created_at descending to get most recent first
            matching_runs.sort(key=lambda r: r.created_at, reverse=True)
            return matching_runs

        sleep(5)

    return []


def dispatch_workflow(
    repository: Repository,
    workflow_filename: str,
    ref: str | Branch,
    inputs: dict[str, str] | None = None,
) -> Workflow:
    """Dispatch a workflow_dispatch workflow.

    Args:
        repository: The repository containing the workflow.
        workflow_filename: The workflow file name (e.g., 'workflow_dispatch_test.yaml').
        ref: The git ref (branch/tag/SHA) to run the workflow on.
        inputs: Dictionary of input parameters for the workflow.

    Returns:
        True if dispatch was successful, False otherwise.
    """
    workflow = repository.get_workflow(workflow_filename)
    assert workflow.create_dispatch(ref=ref, inputs=inputs or {}), (
        "Failed to create dispatch event."
        f"Workflow: {workflow_filename}, Ref: {ref}, Inputs: {inputs}"
    )
    return workflow


def get_workflow_dispatch_run(
    workflow: Workflow,
    ref: str | Branch,
    timeout: int = 120,
    dispatch_time: datetime | None = None,
) -> WorkflowRun:
    """Get the most recent workflow run after dispatching.

    Args:
        workflow: The workflow object.
        ref: The git ref the workflow was dispatched on.
        timeout: Maximum time to wait for the run to appear in seconds.
        dispatch_time: The time the workflow was dispatched. If None, uses \
            current time.

    Returns:
        The most recent workflow run, or None if not found.
    """
    # Record current time as a baseline
    dispatch_time = dispatch_time or datetime.now(timezone.utc)
    start_time = time()

    while time() - start_time < timeout:
        try:
            runs = workflow.get_runs(branch=ref)

            # Find runs created after dispatch time
            for run in runs:
                if run.created_at >= dispatch_time:
                    return run

        except GithubException:
            logger.warning("Error fetching workflow runs", exc_info=True)

        sleep(5)

    raise TimeoutError(f"Timed out waiting for workflow run of {workflow.name} on ref {ref}.")
