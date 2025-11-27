# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for external contributor security configuration."""

import logging
import secrets
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Iterator

import pytest
import yaml
from github import Github
from github.Auth import Token
from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

from .application import RunningApplication
from .factories import GitHubConfig, OpenStackConfig, ProxyConfig, create_default_config
from .github_helpers import (
    close_pull_request,
    create_fork_and_pr,
    get_job_logs,
    get_pr_workflow_runs,
    wait_for_workflow_completion,
)

if TYPE_CHECKING:
    from .factories import TestConfig

logger = logging.getLogger(__name__)

# Test workflow filename
PULL_REQUEST_WORKFLOW_NAME = "Pull request test"


@pytest.fixture(scope="module")
def github_token(github_config: GitHubConfig) -> str:
    """Get GitHub token from github_config.

    Args:
        github_config: GitHub configuration object.

    Returns:
        GitHub personal access token.
    """
    return github_config.token


@pytest.fixture(scope="module")
def github_repository(github_config: GitHubConfig) -> Repository:
    """Get GitHub repository for testing.

    Args:
        github_config: GitHub configuration object.

    Returns:
        GitHub repository object.
    """
    auth = Token(github_config.token)
    github = Github(auth=auth)
    return github.get_repo(github_config.path)


@pytest.fixture(scope="module")
def upstream_repository(github_config: GitHubConfig) -> Repository:
    """Get GitHub repository for testing.

    Args:
        github_config: GitHub configuration object.

    Returns:
        GitHub repository object.
    """
    auth = Token(github_config.alt_token)
    github = Github(auth=auth)
    return github.get_repo(github_config.path)


@pytest.fixture(scope="module")
def forked_github_repository(upstream_repository: Repository) -> Iterator[Repository]:
    """Create a fork of the test repository to simulate external contributor.

    This fixture uses an alternate GitHub token (if provided) to create a fork
    from a different user account, simulating an external contributor scenario.

    Args:
        upstream_repository: The upstream repository using alt token.

    Yields:
        The forked repository.
    """
    # Try to get alternate token for creating fork
    # This simulates a different user (external contributor)

    logger.info(
        "Creating fork of repository %s using alternate token", upstream_repository.full_name
    )
    fork = upstream_repository.create_fork(name=f"test-fork-{secrets.token_hex(4)}")

    logger.info("Waiting for fork to be ready (up to 5 attempts)...")
    # Wait for fork to be ready
    for attempt in range(5):
        try:
            logger.debug("Checking fork readiness (attempt %d/5)", attempt + 1)
            sleep(15)
            fork.get_branches()
            logger.info("Fork is ready: %s", fork.full_name)
            break
        except GithubException:
            pass
    else:
        logger.error("Timed out waiting for fork creation after 5 attempts")
        pytest.fail("Timed out waiting for fork creation")

    yield fork

    # Cleanup: Delete fork (best effort)
    logger.info("Cleaning up: Attempting to delete fork %s", fork.full_name)
    try:
        fork.delete()
        logger.info("Fork deleted successfully")
    except GithubException as e:
        logger.warning(
            "Failed to delete fork %s. Manual cleanup may be required. Error: %s",
            fork.full_name,
            str(e),
        )


@pytest.fixture
def application_with_external_contributor_disabled(
    tmp_path: Path,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig | None,
    test_config: "TestConfig",
    proxy_config: ProxyConfig | None,
) -> Iterator[RunningApplication]:
    """Start application with external contributor checks enabled (disabled access).

    Args:
        tmp_path: Pytest fixture providing temporary directory.
        github_config: GitHub configuration object.
        openstack_config: OpenStack configuration object or None.
        test_config: Test-specific configuration for unique identification.
        proxy_config: Proxy configuration object or None.

    Yields:
        A running application instance.
    """
    config = create_default_config(
        allow_external_contributor=False,
        github_config=github_config,
        openstack_config=openstack_config,
        test_config=test_config,
        proxy_config=proxy_config,
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    logger.info(
        "Starting application with external contributor disabled (test_id: %s)",
        test_config.test_id,
    )
    metrics_log_path = tmp_path / "github-runner-metrics.log"
    app = RunningApplication.create(config_path, metrics_log_path=metrics_log_path)

    yield app

    logger.info("Stopping application")
    app.stop()


@pytest.fixture
def application_with_external_contributor_enabled(
    tmp_path: Path,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig | None,
    test_config: "TestConfig",
    proxy_config: ProxyConfig | None,
) -> Iterator[RunningApplication]:
    """Start application with external contributor checks disabled (permissive mode).

    Args:
        tmp_path: Pytest fixture providing temporary directory.
        github_config: GitHub configuration object.
        openstack_config: OpenStack configuration object or None.
        test_config: Test-specific configuration for unique identification.
        proxy_config: Proxy configuration object or None.

    Yields:
        A running application instance.
    """
    config = create_default_config(
        allow_external_contributor=True,
        github_config=github_config,
        openstack_config=openstack_config,
        test_config=test_config,
        proxy_config=proxy_config,
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    logger.info(
        "Starting application with external contributor enabled (test_id: %s)",
        test_config.test_id,
    )
    metrics_log_path = tmp_path / "github-runner-metrics.log"
    app = RunningApplication.create(config_path, metrics_log_path=metrics_log_path)

    yield app

    logger.info("Stopping application")
    app.stop()


@pytest.fixture
def external_contributor_pull_request(
    upstream_repository: Repository,
    forked_github_repository: Repository,
    test_config: "TestConfig",
) -> Iterator[PullRequest]:
    """Create a pull request from forked repository simulating external contributor.

    Args:
        upstream_repository: The original GitHub repository.
        forked_github_repository: The forked repository (different user).
        test_config: Test configuration with unique identifiers.

    Yields:
        The created pull request.
    """
    logger.info(
        "Creating pull request from fork to simulate external contributor (test_id: %s)",
        test_config.test_id,
    )
    pr = create_fork_and_pr(upstream_repository, forked_github_repository, test_config.test_id)
    logger.info("Pull request created: #%d - %s", pr.number, pr.title)

    yield pr

    # Cleanup: Close the PR
    logger.info("Cleaning up: Closing pull request #%d", pr.number)
    close_pull_request(pr)
    logger.info("Pull request closed successfully")


@pytest.mark.usefixtures(
    "application_with_external_contributor_disabled", "external_contributor_pull_request"
)
def test_external_contributor_disabled_default_security(
    github_repository: Repository, external_contributor_pull_request: PullRequest
):
    """
    arrange: Application running with allow_external_contributor=False, forked repository \
        from external contributor.
    act: Create PR from fork and wait for pull_request_test workflow.
    assert: Workflow fails with "Insufficient user authorization" error in logs.
    """
    logger.info("Test started: test_external_contributor_disabled_default_security")

    # Wait for the pull request workflow to be triggered
    logger.info("Waiting for pull request workflow to be triggered...")
    runs = get_pr_workflow_runs(
        repository=github_repository,
        pr=external_contributor_pull_request,
        workflow_name=PULL_REQUEST_WORKFLOW_NAME,
        timeout=120,
    )
    assert runs, "Pull request workflow should be triggered"
    run = runs[0]
    logger.info("Workflow run found: %s (run_id: %d)", run.html_url, run.id)

    # Wait for the workflow to complete
    logger.info("Waiting for workflow to complete (timeout: 600 seconds)...")
    completed = wait_for_workflow_completion(run, timeout=600)
    assert completed, "Workflow should complete within timeout"
    logger.info("Workflow completed")

    # Verify the workflow failed due to security check
    run.update()
    logger.info("Workflow conclusion: %s", run.conclusion)
    assert run.conclusion == "failure", (
        f"Workflow should fail when external contributor is blocked. "
        f"Got conclusion: {run.conclusion}"
    )

    # Get the job logs and verify the failure reason
    logger.info("Retrieving job logs to verify failure reason...")
    logs = get_job_logs(run)
    assert "Insufficient user authorization" in logs or "author_association" in logs, (
        "Logs should indicate external contributor was blocked. " f"Actual logs: {logs[:500]}"
    )


@pytest.mark.usefixtures(
    "application_with_external_contributor_enabled", "external_contributor_pull_request"
)
def test_external_contributor_enabled_permissive_mode(
    github_repository: Repository, external_contributor_pull_request: PullRequest
):
    """
    arrange: Application running with allow_external_contributor=True, forked repository \
        from external contributor.
    act: Create PR from fork and wait for pull_request_test workflow.
    assert: Workflow succeeds with no authorization errors in logs.
    """
    logger.info("Test started: test_external_contributor_enabled_permissive_mode")

    # Wait for the pull request workflow to be triggered
    logger.info("Waiting for pull request workflow to be triggered...")
    runs = get_pr_workflow_runs(
        repository=github_repository,
        pr=external_contributor_pull_request,
        workflow_name=PULL_REQUEST_WORKFLOW_NAME,
        timeout=120,
    )
    assert runs, "Pull request workflow should be triggered"
    run = runs[0]
    logger.info("Workflow run found: %s (run_id: %d)", run.html_url, run.id)

    # Wait for the workflow to complete
    logger.info("Waiting for workflow to complete (timeout: 600 seconds)...")
    completed = wait_for_workflow_completion(run, timeout=600)
    assert completed, "Workflow should complete within timeout"
    logger.info("Workflow completed")

    # Verify the workflow succeeded (external contributor allowed)
    run.update()
    logger.info("Workflow conclusion: %s", run.conclusion)
    assert run.conclusion == "success", (
        f"Workflow should succeed when external contributor is allowed. "
        f"Got conclusion: {run.conclusion}"
    )

    # Get the job logs and verify it ran successfully
    logger.info("Retrieving job logs to verify success...")
    logs = get_job_logs(run)
    assert "Should not echo if pre-job script failed" in logs, (
        "Logs should contain the expected success message. " f"Actual logs: {logs[:500]}"
    )

    # Ensure no security errors in logs
    assert (
        "Insufficient user authorization" not in logs
    ), "Logs should not contain security errors when external contributor is allowed"
