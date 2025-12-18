# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for pre-job script template and execution."""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict

import pytest
from jinja2 import Template

# GitHub Actions default environment variables that are always present
# Reference:
# https://docs.github.com/en/actions/reference/workflows-and-actions/variables
GITHUB_DEFAULT_ENV_VARS = {
    "CI": "true",
    "GITHUB_ACTION": "__run",
    "GITHUB_ACTIONS": "true",
    "GITHUB_ACTOR": "test-user",
    "GITHUB_API_URL": "https://api.github.com",
    "GITHUB_BASE_REF": "",
    "GITHUB_ENV": "/tmp/github_env",
    "GITHUB_EVENT_NAME": "pull_request",
    "GITHUB_EVENT_PATH": "",  # Will be set dynamically in tests
    "GITHUB_GRAPHQL_URL": "https://api.github.com/graphql",
    "GITHUB_HEAD_REF": "feature-branch",
    "GITHUB_JOB": "test-job",
    "GITHUB_PATH": "/tmp/github_path",
    "GITHUB_REF": "refs/pull/123/merge",
    "GITHUB_REF_NAME": "123/merge",
    "GITHUB_REF_TYPE": "branch",
    "GITHUB_REPOSITORY": "canonical/github-runner-operator",
    "GITHUB_REPOSITORY_OWNER": "canonical",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "1234567890",
    "GITHUB_RUN_NUMBER": "42",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_SHA": "abc123def456",
    "GITHUB_WORKFLOW": "Test Workflow",
    "GITHUB_WORKSPACE": "/home/runner/work/repo/repo",
    "RUNNER_ARCH": "X64",
    "RUNNER_NAME": "test-runner",
    "RUNNER_OS": "Linux",
    "RUNNER_TEMP": "/tmp",
    "RUNNER_TOOL_CACHE": "/opt/hostedtoolcache",
}

# PR-related event types that support fork detection
PR_EVENTS = [
    "pull_request",
    "pull_request_target",
    "pull_request_review",
    "pull_request_review_comment",
]

LOG_SKIPPED_CHECK = "Contributor check skipped for event:"
LOG_INTERNAL_PR = "Internal PR detected - contributor check skipped"
LOG_FORK_PR_CHECK = "Fork PR or missing repository detected - performing contributor check"
LOG_AUTH_FAILED = (
    "Insufficient user authorization - only OWNER, MEMBER, or COLLABORATOR may run workflows"
)
LOG_CHECK_PASSED = "Contributor check passed - proceeding to execute jobs"


@pytest.fixture
def pre_job_template() -> Template:
    """Load the pre-job.j2 template."""
    template_path = (
        Path(__file__).parent.parent.parent / "src/github_runner_manager/templates/pre-job.j2"
    )
    return Template(template_path.read_text())


@pytest.fixture
def github_env_vars(tmp_path: Path) -> Dict[str, str]:
    """Provide GitHub Actions environment variables with temporary paths.

    This fixture can be used as a base for parameterized tests requiring
    different GitHub event contexts.
    """
    env_vars = GITHUB_DEFAULT_ENV_VARS.copy()
    # Create temporary files for GitHub Actions file-based environment variables
    env_vars["GITHUB_ENV"] = str(tmp_path / "github_env")
    env_vars["GITHUB_PATH"] = str(tmp_path / "github_path")
    # GITHUB_EVENT_PATH will be set per test
    env_vars["GITHUB_EVENT_PATH"] = str(tmp_path / "event.json")

    # Ensure PATH is set for subprocess execution
    env_vars["PATH"] = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")

    return env_vars


@pytest.fixture
def default_template_vars() -> Dict:
    """Provide default template variables for pre-job script rendering.

    This fixture returns the most common configuration with allow_external_contributor
    disabled. Tests can override specific values as needed.
    """
    return {
        "allow_external_contributor": False,
        "issue_metrics": False,
        "do_repo_policy_check": False,
        "dockerhub_mirror": "",
        "custom_pre_job_script": "",
    }


def _create_github_event_payload(
    author_association: str,
    event_type: str = "pull_request",
    is_fork: bool = False,
    is_private: bool = False,
) -> Dict:
    """Create a GitHub event payload for testing.

    Args:
        author_association: The author's association with the repository
            (OWNER, MEMBER, COLLABORATOR, CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, NONE, etc.)
        event_type: The type of GitHub event (pull_request, push, issue_comment, etc.)
        is_fork: Whether to simulate a fork PR (only applies to PR events)
        is_private: Whether the repository is private

    Returns:
        A dictionary representing the GitHub event payload
    """
    # Base payload common to all events
    base_payload = {
        "repository": {
            "name": "github-runner-operator",
            "full_name": "canonical/github-runner-operator",
            "private": is_private,
            "owner": {
                "login": "canonical",
            },
        },
        "sender": {
            "login": "test-user",
        },
    }

    # Determine head repo based on is_fork parameter
    head_repo_full_name = (
        "external-user/github-runner-operator" if is_fork else "canonical/github-runner-operator"
    )

    # Event-specific payloads
    if event_type == "pull_request":
        return {
            **base_payload,
            "action": "opened",
            "number": 123,
            "pull_request": {
                "author_association": author_association,
                "number": 123,
                "title": "Test PR",
                "user": {
                    "login": "test-user",
                    "type": "User",
                },
                "head": {
                    "ref": "feature-branch",
                    "sha": "abc123",
                    "repo": {
                        "full_name": head_repo_full_name,
                    },
                },
                "base": {
                    "ref": "main",
                    "sha": "def456",
                    "repo": {
                        "full_name": "canonical/github-runner-operator",
                    },
                },
            },
        }

    elif event_type == "pull_request_target":
        return {
            **base_payload,
            "action": "opened",
            "number": 123,
            "pull_request": {
                "author_association": author_association,
                "number": 123,
                "title": "Test PR Target",
                "user": {
                    "login": "test-user",
                    "type": "User",
                },
                "head": {
                    "ref": "feature-branch",
                    "sha": "abc123",
                    "repo": {
                        "full_name": head_repo_full_name,
                    },
                },
                "base": {
                    "ref": "main",
                    "sha": "def456",
                    "repo": {
                        "full_name": "canonical/github-runner-operator",
                    },
                },
            },
        }

    elif event_type == "pull_request_review":
        return {
            **base_payload,
            "action": "submitted",
            "pull_request": {
                "number": 123,
                "title": "Test PR for Review",
                "head": {
                    "ref": "feature-branch",
                    "sha": "abc123",
                    "repo": {
                        "full_name": head_repo_full_name,
                    },
                },
                "base": {
                    "ref": "main",
                    "sha": "def456",
                    "repo": {
                        "full_name": "canonical/github-runner-operator",
                    },
                },
            },
            "review": {
                "author_association": author_association,
                "user": {
                    "login": "test-user",
                },
                "state": "approved",
                "body": "LGTM",
            },
        }

    elif event_type == "pull_request_review_comment":
        return {
            **base_payload,
            "action": "created",
            "pull_request": {
                "number": 123,
                "title": "Test PR for Review Comment",
                "head": {
                    "ref": "feature-branch",
                    "sha": "abc123",
                    "repo": {
                        "full_name": head_repo_full_name,
                    },
                },
                "base": {
                    "ref": "main",
                    "sha": "def456",
                    "repo": {
                        "full_name": "canonical/github-runner-operator",
                    },
                },
            },
            "comment": {
                "author_association": author_association,
                "user": {
                    "login": "test-user",
                },
                "body": "Good catch!",
            },
        }

    elif event_type == "issue_comment":
        return {
            **base_payload,
            "action": "created",
            "issue": {
                "author_association": author_association,
                "number": 456,
                "title": "Test Issue",
                "user": {
                    "login": "test-user",
                },
            },
            "comment": {
                "author_association": author_association,
                "user": {
                    "login": "test-user",
                },
                "body": "This is a comment",
            },
        }

    elif event_type == "push":
        return {
            **base_payload,
            "ref": "refs/heads/main",
            "before": "def456",
            "after": "abc123",
            "commits": [
                {
                    "id": "abc123",
                    "message": "Test commit",
                    "author": {
                        "name": "test-user",
                        "email": "test@example.com",
                    },
                }
            ],
        }

    elif event_type == "workflow_dispatch":
        return {
            **base_payload,
            "ref": "refs/heads/main",
            "inputs": {},
        }

    elif event_type == "schedule":
        return {
            **base_payload,
            "schedule": "0 0 * * *",
        }

    else:
        # Default fallback for unknown event types
        return {
            **base_payload,
            "action": "unknown",
        }


def render_and_execute_script(
    template: Template,
    template_vars: Dict,
    env_vars: Dict[str, str],
    github_event: Dict,
    tmp_path: Path,
) -> subprocess.CompletedProcess:
    """Render the pre-job template and execute it with given environment.

    Args:
        template: The Jinja2 template to render
        template_vars: Variables to pass to the template
        env_vars: Environment variables for script execution
        github_event: GitHub event payload to write to GITHUB_EVENT_PATH
        tmp_path: Temporary directory for files

    Returns:
        CompletedProcess with the result of script execution
    """
    # Render the template
    script_content = template.render(**template_vars)
    script_path = tmp_path / "pre-job.sh"
    script_path.write_text(script_content)
    script_path.chmod(0o755)

    # Write GitHub event payload
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(github_event))
    env_vars["GITHUB_EVENT_PATH"] = str(event_path)

    # Execute the script
    return subprocess.run(
        [str(script_path)],
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    "author_association",
    ["OWNER", "MEMBER", "COLLABORATOR"],
)
def test_allow_external_contributor_disabled_allows_trusted_roles(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    default_template_vars: Dict,
):
    """Test that OWNER/MEMBER/COLLABORATOR are all allowed (for fork PRs)."""
    fork_event = _create_github_event_payload(
        author_association=author_association,
        is_fork=True,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=fork_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == 0, (
        f"Expected exit code 0 for {author_association}, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert f"Author association: {author_association}, is allowed: true" in result.stderr
    assert LOG_CHECK_PASSED in result.stderr
    assert LOG_AUTH_FAILED not in result.stderr


@pytest.mark.parametrize(
    "author_association",
    ["CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"],
)
def test_allow_external_contributor_disabled_blocks_untrusted_roles(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    default_template_vars: Dict,
):
    """Test that untrusted author associations are blocked (for fork PRs)."""
    fork_event = _create_github_event_payload(
        author_association=author_association,
        is_fork=True,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=fork_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == 1, (
        f"Expected exit code 1 for {author_association}, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert f"Author association: {author_association}, is allowed: false" in result.stderr
    assert LOG_AUTH_FAILED in result.stderr


def test_allow_external_contributor_enabled_skips_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    default_template_vars: Dict,
):
    """Test that check is skipped when allow_external_contributor=True."""
    template_vars = {**default_template_vars, "allow_external_contributor": True}

    # Even with CONTRIBUTOR, script should succeed
    github_event = _create_github_event_payload(author_association="CONTRIBUTOR")

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=template_vars,
        env_vars=github_env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert (
        result.returncode == 0
    ), f"Expected exit code 0, got {result.returncode}\nstderr: {result.stderr}"
    # The check wasn't performed, so these messages shouldn't appear
    assert "AUTHOR_ASSOCIATION" not in result.stderr
    assert LOG_AUTH_FAILED not in result.stderr
    assert LOG_CHECK_PASSED not in result.stderr


@pytest.mark.parametrize(
    "author_association,should_pass",
    [
        ("OWNER", True),
        ("MEMBER", True),
        ("COLLABORATOR", True),
        ("CONTRIBUTOR", True),  # Allowed for private repos
        ("FIRST_TIME_CONTRIBUTOR", False),  # Still blocked
        ("NONE", False),  # Still blocked
    ],
)
def test_private_repository_allows_contributor(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    should_pass: bool,
    default_template_vars: Dict,
):
    """Test that private repositories extend allowed authorizations to include CONTRIBUTOR.

    Private repositories trust CONTRIBUTORs since they have repository access,
    but still block FIRST_TIME_CONTRIBUTOR and NONE.
    """
    # Create a fork PR event for a private repository
    private_repo_event = _create_github_event_payload(
        author_association=author_association,
        is_fork=True,
        is_private=True,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=private_repo_event,
        tmp_path=tmp_path,
    )

    if should_pass:
        assert result.returncode == 0, (
            f"Expected exit code 0 for private repository with {author_association}, "
            f"got {result.returncode}\nstderr: {result.stderr}"
        )
        assert "Private repository - extended authorization includes CONTRIBUTOR" in result.stderr
        assert LOG_AUTH_FAILED not in result.stderr
    else:
        assert result.returncode == 1, (
            f"Expected exit code 1 for private repository with {author_association}, "
            f"got {result.returncode}\nstderr: {result.stderr}"
        )
        assert LOG_AUTH_FAILED in result.stderr


def test_public_repository_blocks_contributor(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    default_template_vars: Dict,
):
    """Test that public repositories still block CONTRIBUTOR role.

    This ensures the behavior change only applies to private repositories.
    """
    # Create a fork PR event for a public repository with CONTRIBUTOR
    public_repo_event = _create_github_event_payload(
        author_association="CONTRIBUTOR",
        is_fork=True,
        is_private=False,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=public_repo_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == 1, (
        f"Expected exit code 1 for public repository with CONTRIBUTOR, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )
    assert f"Author association: CONTRIBUTOR, is allowed: false" in result.stderr
    assert LOG_AUTH_FAILED in result.stderr
    # Should not see private repo message for public repos
    assert "Private repository - extended authorization includes CONTRIBUTOR" not in result.stderr


@pytest.mark.parametrize(
    "github_event,description",
    [
        pytest.param(
            {
                "ref": "refs/heads/main",
                "repository": {
                    "name": "github-runner-operator",
                    "full_name": "canonical/github-runner-operator",
                },
            },
            "missing pull_request field (push event)",
            id="no_pull_request",
        ),
        pytest.param(
            {
                "pull_request": {
                    "number": 123,
                    "title": "Test PR",
                },
                "repository": {
                    "name": "github-runner-operator",
                },
            },
            "missing author_association field",
            id="no_author_association",
        ),
    ],
)
def test_allow_external_contributor_null_or_missing_fields_blocked(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    github_event: Dict,
    description: str,
    default_template_vars: Dict,
):
    """Test that null/missing fields are blocked when check is enabled."""
    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    # When pull_request or author_association is missing, jq returns empty string
    # The check should fail as "" != "OWNER|MEMBER|COLLABORATOR"
    assert result.returncode == 1, (
        f"Expected exit code 1 for {description}, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert "Author association: " in result.stderr
    assert LOG_AUTH_FAILED in result.stderr


@pytest.mark.parametrize(
    "event_type,author_association,expected_exit_code,expected_logs",
    [
        # Events that trigger author association checks - success cases
        pytest.param(
            "pull_request",
            "OWNER",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_owner_allowed",
        ),
        pytest.param(
            "pull_request",
            "MEMBER",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_member_allowed",
        ),
        pytest.param(
            "pull_request",
            "COLLABORATOR",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_collaborator_allowed",
        ),
        # Events that trigger author association checks - failure cases
        pytest.param(
            "pull_request",
            "CONTRIBUTOR",
            1,
            [
                LOG_AUTH_FAILED,
                LOG_FORK_PR_CHECK,
            ],
            id="pr_contributor_blocked",
        ),
        pytest.param(
            "pull_request_target",
            "OWNER",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_target_owner_allowed",
        ),
        pytest.param(
            "pull_request_target",
            "CONTRIBUTOR",
            1,
            [
                LOG_AUTH_FAILED,
                LOG_FORK_PR_CHECK,
            ],
            id="pr_target_contributor_blocked",
        ),
        pytest.param(
            "pull_request_review",
            "MEMBER",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_review_member_allowed",
        ),
        pytest.param(
            "pull_request_review",
            "FIRST_TIME_CONTRIBUTOR",
            1,
            [
                LOG_AUTH_FAILED,
                LOG_FORK_PR_CHECK,
            ],
            id="pr_review_first_time_blocked",
        ),
        pytest.param(
            "pull_request_review_comment",
            "COLLABORATOR",
            0,
            [LOG_CHECK_PASSED, LOG_FORK_PR_CHECK],
            id="pr_review_comment_collaborator_allowed",
        ),
        pytest.param(
            "pull_request_review_comment",
            "NONE",
            1,
            [
                LOG_AUTH_FAILED,
                LOG_FORK_PR_CHECK,
            ],
            id="pr_review_comment_none_blocked",
        ),
        pytest.param(
            "issue_comment",
            "OWNER",
            0,
            [LOG_CHECK_PASSED],
            id="issue_comment_owner_allowed",
        ),
        pytest.param(
            "issue_comment",
            "CONTRIBUTOR",
            1,
            [
                LOG_AUTH_FAILED,
            ],
            id="issue_comment_contributor_blocked",
        ),
        # Events that skip author association checks
        pytest.param(
            "push",
            "CONTRIBUTOR",
            0,
            [LOG_SKIPPED_CHECK],
            id="push_skipped",
        ),
        pytest.param(
            "workflow_dispatch",
            "CONTRIBUTOR",
            0,
            [LOG_SKIPPED_CHECK],
            id="workflow_dispatch_skipped",
        ),
        pytest.param(
            "schedule",
            "CONTRIBUTOR",
            0,
            [LOG_SKIPPED_CHECK],
            id="schedule_skipped",
        ),
    ],
)
def test_author_association_check_by_event_type(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    event_type: str,
    author_association: str,
    expected_exit_code: int,
    expected_logs: list,
    default_template_vars: Dict,
):
    """Test author association checks for different GitHub event types."""
    # Update environment to match the event type
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # For PR-related events (except issue_comment), make them fork PRs to test author
    # association logic. Internal PRs skip the check, so we need fork PRs to test the
    # actual authorization logic
    is_fork = event_type in PR_EVENTS

    event_payload = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
        is_fork=is_fork,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=event_payload,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for {event_type} with {author_association}, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    # Check for expected log messages
    for log_message in expected_logs:
        assert (
            log_message in result.stderr
        ), f"Expected log message '{log_message}' not found in stderr: {result.stderr}"


@pytest.mark.parametrize(
    "workflow_name,expected_exit_code,expected_logs",
    [
        # Pull request events - these are internal PRs (same repo)
        pytest.param(
            "pull_request",
            0,
            [LOG_INTERNAL_PR, LOG_CHECK_PASSED],
            id="real_pull_request_internal",
        ),
        pytest.param(
            "pull_request_target",
            0,
            [LOG_INTERNAL_PR, LOG_CHECK_PASSED],
            id="real_pull_request_target_internal",
        ),
        pytest.param(
            "pull_request_review",
            0,
            [LOG_INTERNAL_PR, LOG_CHECK_PASSED],
            id="real_pull_request_review_internal",
        ),
        # Issue comment - always performs author association check
        pytest.param(
            "issue_comment",
            0,
            [LOG_CHECK_PASSED],
            id="real_issue_comment_owner",
        ),
        # Events that skip contributor checks
        pytest.param(
            "push",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_push_skipped",
        ),
        pytest.param(
            "workflow_dispatch",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_workflow_dispatch_skipped",
        ),
        pytest.param(
            "release",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_release_skipped",
        ),
        pytest.param(
            "create",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_create_skipped",
        ),
        pytest.param(
            "delete",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_delete_skipped",
        ),
        pytest.param(
            "issues",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_issues_skipped",
        ),
        pytest.param(
            "label",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_label_skipped",
        ),
        pytest.param(
            "gollum",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_gollum_skipped",
        ),
        pytest.param(
            "discussion",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_discussion_skipped",
        ),
        pytest.param(
            "discussion_comment",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_discussion_comment_skipped",
        ),
        pytest.param(
            "branch_protection_rule",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_branch_protection_rule_skipped",
        ),
        pytest.param(
            "workflow_run",
            0,
            [LOG_SKIPPED_CHECK],
            id="real_workflow_run_skipped",
        ),
    ],
)
def test_pre_job_script_with_real_workflow_data(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    workflow_name: str,
    expected_exit_code: int,
    expected_logs: list,
    default_template_vars: Dict,
):
    """Test pre-job script behavior using real GitHub workflow event data.

    This test uses actual GitHub event payloads from tests/data/workflows/
    to verify that the pre-job script handles real-world scenarios correctly.

    arrange: Given a real GitHub event payload from the test data directory
    act: When the pre-job script is executed with the real event data
    assert: The script exits with the expected code and logs the expected messages
    """
    # Load real workflow data
    workflow_data_path = (
        Path(__file__).parent.parent / "data" / "workflows" / f"{workflow_name}.json"
    )

    assert workflow_data_path.exists(), f"Workflow data file not found: {workflow_data_path}"

    with open(workflow_data_path) as f:
        github_event = json.load(f)

    # Update environment to match the event type
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = workflow_name

    # For PR events, update repo info from the real data
    if "pull_request" in workflow_name and "repository" in github_event:
        repo_info = github_event["repository"]
        env_vars["GITHUB_REPOSITORY"] = repo_info["full_name"]
        env_vars["GITHUB_REPOSITORY_OWNER"] = repo_info["owner"]["login"]

    # For push events, update repo and ref info
    if workflow_name == "push" and "repository" in github_event:
        repo_info = github_event["repository"]
        env_vars["GITHUB_REPOSITORY"] = repo_info["full_name"]
        env_vars["GITHUB_REPOSITORY_OWNER"] = repo_info["owner"]["login"]
        if "ref" in github_event:
            env_vars["GITHUB_REF"] = github_event["ref"]

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for real {workflow_name} event, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    # Check for expected log messages
    for log_message in expected_logs:
        assert (
            log_message in result.stderr
        ), f"Expected log message '{log_message}' not found in stderr: {result.stderr}"


@pytest.mark.parametrize(
    "event_type",
    [
        "push",
        "workflow_dispatch",
        "schedule",
        "release",
        "deployment",
        "unknown_event",
    ],
)
def test_events_skip_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    event_type: str,
    default_template_vars: Dict,
):
    """Test that non-contributor events skip the author association check."""
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    github_event = _create_github_event_payload(
        author_association="CONTRIBUTOR",  # This would normally be blocked
        event_type=event_type,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    # All these events should succeed regardless of author association
    assert (
        result.returncode == 0
    ), f"Expected exit code 0 for {event_type}, got {result.returncode}\nstderr: {result.stderr}"

    # Should skip the contributor check
    assert f"Contributor check skipped for event: {event_type}" in result.stderr
    assert LOG_AUTH_FAILED not in result.stderr


@pytest.mark.parametrize(
    "author_association,event_type",
    [
        pytest.param("CONTRIBUTOR", "pull_request", id="pr_internal_contributor"),
        pytest.param("FIRST_TIME_CONTRIBUTOR", "pull_request", id="pr_internal_first_time"),
        pytest.param("NONE", "pull_request", id="pr_internal_none"),
        pytest.param("CONTRIBUTOR", "pull_request_target", id="pr_target_internal_contributor"),
        pytest.param("CONTRIBUTOR", "pull_request_review", id="pr_review_internal_contributor"),
        pytest.param(
            "CONTRIBUTOR",
            "pull_request_review_comment",
            id="pr_review_comment_internal_contributor",
        ),
    ],
)
def test_internal_pr_skips_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    event_type: str,
    default_template_vars: Dict,
):
    """Test that internal PRs skip author association checks.

    arrange: given an internal PR event (head and base repos match) with any author association.
    act: when the pre-job script is executed.
    assert: the author association check is skipped and the script succeeds regardless of the
        author's association level.
    """
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # Create payload with matching head and base repo (internal PR)
    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
        is_fork=False,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    # Internal PR should succeed regardless of author association
    assert result.returncode == 0, (
        f"Expected exit code 0 for internal {event_type} with {author_association}, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    # Should log that it's an internal PR and skip the check
    assert LOG_INTERNAL_PR in result.stderr
    assert LOG_CHECK_PASSED in result.stderr
    # Should NOT perform the author association check
    assert LOG_AUTH_FAILED not in result.stderr


@pytest.mark.parametrize(
    "author_association,expected_exit_code,event_type,expected_log",
    [
        pytest.param(
            "OWNER",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="fork_pr_owner_allowed",
        ),
        pytest.param(
            "MEMBER",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="fork_pr_member_allowed",
        ),
        pytest.param(
            "COLLABORATOR",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="fork_pr_collaborator_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            "pull_request",
            LOG_AUTH_FAILED,
            id="fork_pr_contributor_blocked",
        ),
        pytest.param(
            "FIRST_TIME_CONTRIBUTOR",
            1,
            "pull_request",
            LOG_AUTH_FAILED,
            id="fork_pr_first_time_blocked",
        ),
        pytest.param(
            "NONE",
            1,
            "pull_request",
            LOG_AUTH_FAILED,
            id="fork_pr_none_blocked",
        ),
        pytest.param(
            "OWNER",
            0,
            "pull_request_target",
            LOG_CHECK_PASSED,
            id="fork_pr_target_owner_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            "pull_request_target",
            LOG_AUTH_FAILED,
            id="fork_pr_target_contributor_blocked",
        ),
        pytest.param(
            "MEMBER",
            0,
            "pull_request_review",
            LOG_CHECK_PASSED,
            id="fork_pr_review_member_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            "pull_request_review",
            LOG_AUTH_FAILED,
            id="fork_pr_review_contributor_blocked",
        ),
        pytest.param(
            "COLLABORATOR",
            0,
            "pull_request_review_comment",
            LOG_CHECK_PASSED,
            id="fork_pr_review_comment_collaborator_allowed",
        ),
        pytest.param(
            "NONE",
            1,
            "pull_request_review_comment",
            LOG_AUTH_FAILED,
            id="fork_pr_review_comment_none_blocked",
        ),
    ],
)
def test_fork_pr_performs_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    expected_exit_code: int,
    event_type: str,
    expected_log: str,
    default_template_vars: Dict,
):
    """Test that fork PRs perform author association checks.

    arrange: given a fork PR event (head and base repos differ) with a specific author association.
    act: when the pre-job script is executed.
    assert: the author association check is performed and the script exits with the expected code
        based on whether the author has sufficient permissions (OWNER/MEMBER/COLLABORATOR).
    """
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # Create payload with different head and base repo (fork PR)
    fork_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
        is_fork=True,
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=fork_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for fork {event_type} with "
        f"{author_association}, got {result.returncode}\nstderr: {result.stderr}"
    )
    assert (
        LOG_FORK_PR_CHECK in result.stderr
    ), f"Expected log message '{LOG_FORK_PR_CHECK}' not found in stderr: {result.stderr}"
    assert (
        expected_log in result.stderr
    ), f"Expected log message '{expected_log}' not found in stderr: {result.stderr}"


@pytest.mark.parametrize(
    "author_association,expected_exit_code,event_type,expected_log",
    [
        pytest.param(
            "OWNER",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="missing_repo_owner_allowed",
        ),
        pytest.param(
            "MEMBER",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="missing_repo_member_allowed",
        ),
        pytest.param(
            "COLLABORATOR",
            0,
            "pull_request",
            LOG_CHECK_PASSED,
            id="missing_repo_collaborator_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            "pull_request",
            LOG_AUTH_FAILED,
            id="missing_repo_contributor_blocked",
        ),
        pytest.param(
            "OWNER",
            0,
            "pull_request_target",
            LOG_CHECK_PASSED,
            id="missing_repo_target_owner_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            "pull_request_target",
            LOG_AUTH_FAILED,
            id="missing_repo_target_contributor_blocked",
        ),
    ],
)
def test_missing_repo_info_performs_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    expected_exit_code: int,
    event_type: str,
    expected_log: str,
    default_template_vars: Dict,
):
    """Test author association check when repository information is missing.

    arrange: given a PR event with missing repository information and a specific author
        association.
    act: when the pre-job script is executed.
    assert: the author association check is performed as a safety fallback and the script exits
        with the expected code based on the author's permissions.
    """
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # Create payload without repo information
    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
    )
    # Remove repo info from head
    if "pull_request" in github_event and "head" in github_event["pull_request"]:
        if "repo" in github_event["pull_request"]["head"]:
            del github_event["pull_request"]["head"]["repo"]

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for {event_type} with missing repo info "
        f"and {author_association}, got {result.returncode}\nstderr: {result.stderr}"
    )

    assert (
        LOG_FORK_PR_CHECK in result.stderr
    ), f"Expected log message '{LOG_FORK_PR_CHECK}' not found in stderr: {result.stderr}"
    assert (
        expected_log in result.stderr
    ), f"Expected log message '{expected_log}' not found in stderr: {result.stderr}"


@pytest.mark.parametrize(
    "author_association,expected_exit_code,expected_log",
    [
        pytest.param(
            "OWNER",
            0,
            LOG_CHECK_PASSED,
            id="issue_comment_owner_allowed",
        ),
        pytest.param(
            "MEMBER",
            0,
            LOG_CHECK_PASSED,
            id="issue_comment_member_allowed",
        ),
        pytest.param(
            "COLLABORATOR",
            0,
            LOG_CHECK_PASSED,
            id="issue_comment_collaborator_allowed",
        ),
        pytest.param(
            "CONTRIBUTOR",
            1,
            LOG_AUTH_FAILED,
            id="issue_comment_contributor_blocked",
        ),
        pytest.param(
            "FIRST_TIME_CONTRIBUTOR",
            1,
            LOG_AUTH_FAILED,
            id="issue_comment_first_time_blocked",
        ),
        pytest.param(
            "NONE",
            1,
            LOG_AUTH_FAILED,
            id="issue_comment_none_blocked",
        ),
    ],
)
def test_issue_comment_always_performs_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    expected_exit_code: int,
    expected_log: str,
    default_template_vars: Dict,
):
    """Test that issue_comment events always perform author association checks.

    arrange: given an issue_comment event with a specific author association.
    act: when the pre-job script is executed.
    assert: the author association check is always performed (no fork detection for issue_comment
        events) and the script exits with the expected code based on the author's permissions.
    """
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = "issue_comment"

    # Create issue_comment event payload
    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type="issue_comment",
    )

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for issue_comment with {author_association}, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    assert (
        expected_log in result.stderr
    ), f"Expected log message '{expected_log}' not found in stderr: {result.stderr}"
