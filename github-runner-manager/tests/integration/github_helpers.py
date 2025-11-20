# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper functions for GitHub integration testing."""

from datetime import datetime, timezone
from time import sleep

import requests
from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun


def create_fork_and_pr(
    github_repository: Repository,
    forked_github_repository: Repository,
    test_id: str,
) -> PullRequest:
    """Create a PR from a forked repository.

    Args:
        github_repository: The original repository.
        forked_github_repository: The forked repository.
        test_id: Unique test identifier.

    Returns:
        The created pull request.
    """
    # Create a unique branch in the fork
    branch_name = f"test/{test_id}"
    main_branch = forked_github_repository.get_branch(github_repository.default_branch)
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
    pr = github_repository.create_pull(
        title=f"Test PR from fork {test_id}",
        body=f"This is a test PR from a forked repository for testing external contributor security. Test ID: {test_id}",
        head=f"{forked_github_repository.owner.login}:{branch_name}",
        base=github_repository.default_branch,
    )

    return pr


def dispatch_workflow_and_get_run(
    repository: Repository,
    workflow_filename: str,
    runner_label: str,
) -> WorkflowRun | None:
    """Dispatch a workflow and return the workflow run.

    Args:
        repository: Repository to dispatch workflow on.
        workflow_filename: Workflow file to dispatch.
        runner_label: Runner label to target.

    Returns:
        The workflow run object, or None if not found.
    """
    start_time = datetime.now(timezone.utc)
    workflow = repository.get_workflow(id_or_file_name=workflow_filename)

    # Dispatch the workflow
    success = workflow.create_dispatch(
        ref=repository.default_branch,
        inputs={"runner": runner_label},
    )

    if not success:
        return None

    # Wait for the workflow run to appear (up to 2 minutes)
    for _ in range(24):  # 24 * 5 = 120 seconds
        sleep(5)
        runs = workflow.get_runs(created=f">={start_time.isoformat(timespec='seconds')}")
        if runs.totalCount > 0:
            return runs[0]

    return None


def wait_for_workflow_completion(run: WorkflowRun, timeout: int = 600) -> bool:
    """Wait for a workflow run to complete.

    Args:
        run: The workflow run to wait for.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if workflow completed, False if timeout.
    """
    iterations = timeout // 10
    for _ in range(iterations):
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

    job = jobs[0]
    logs_url = job.logs_url()
    response = requests.get(logs_url)
    return response.content.decode("utf-8")


def close_pull_request(pr: PullRequest) -> None:
    """Close a pull request (best effort).

    Args:
        pr: The pull request to close.
    """
    try:
        pr.edit(state="closed")
    except GithubException:
        pass  # Best effort cleanup
