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
PR_EVENTS = ["pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment"]



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
) -> Dict:
    """Create a GitHub event payload for testing.

    Args:
        author_association: The author's association with the repository
            (OWNER, MEMBER, COLLABORATOR, CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, NONE, etc.)
        event_type: The type of GitHub event (pull_request, push, issue_comment, etc.)

    Returns:
        A dictionary representing the GitHub event payload
    """
    # Base payload common to all events
    base_payload = {
        "repository": {
            "name": "github-runner-operator",
            "full_name": "canonical/github-runner-operator",
            "owner": {
                "login": "canonical",
            },
        },
        "sender": {
            "login": "test-user",
        },
    }

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
                        "full_name": "canonical/github-runner-operator",
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
                        "full_name": "canonical/github-runner-operator",
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
                        "full_name": "canonical/github-runner-operator",
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
                        "full_name": "canonical/github-runner-operator",
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


def _make_fork_pr(github_event: Dict, fork_repo: str = "external-user/github-runner-operator") -> Dict:
    """Convert a GitHub event payload to simulate a fork PR.
    
    Args:
        github_event: The base GitHub event payload
        fork_repo: The full name of the fork repository (default: external-user/github-runner-operator)
    
    Returns:
        Modified event payload with head repo set to fork
    """
    if "pull_request" in github_event and "head" in github_event["pull_request"]:
        if "repo" in github_event["pull_request"]["head"]:
            github_event["pull_request"]["head"]["repo"]["full_name"] = fork_repo
    return github_event


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
    github_event = _create_github_event_payload(author_association=author_association)
    # Make it a fork PR to test the author association logic
    _make_fork_pr(github_event)

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == 0, (
        f"Expected exit code 0 for {author_association}, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert f"Author association: {author_association}" in result.stderr
    assert "The contributor check has passed, proceeding to execute jobs" in result.stderr
    assert "Insufficient user authorization" not in result.stderr


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
    github_event = _create_github_event_payload(author_association=author_association)
    # Make it a fork PR to test the author association logic
    _make_fork_pr(github_event)

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=github_env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == 1, (
        f"Expected exit code 1 for {author_association}, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert f"Author association: {author_association}" in result.stderr
    assert "Insufficient user authorization (author_association)" in result.stderr
    assert "Only OWNER, MEMBER, or COLLABORATOR may run workflows" in result.stderr


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
    assert "Insufficient user authorization" not in result.stderr
    assert "The contributor check has passed" not in result.stderr


@pytest.mark.parametrize(
    "github_event,description",
    [
        (
            {
                "ref": "refs/heads/main",
                "repository": {
                    "name": "github-runner-operator",
                    "full_name": "canonical/github-runner-operator",
                },
            },
            "missing pull_request field (push event)",
        ),
        (
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
        ),
    ],
    ids=["no_pull_request", "no_author_association"],
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
    assert "Insufficient user authorization" in result.stderr


@pytest.mark.parametrize(
    "event_type,author_association,expected_exit_code",
    [
        # Events that trigger author association checks
        ("pull_request", "OWNER", 0),
        ("pull_request", "MEMBER", 0),
        ("pull_request", "COLLABORATOR", 0),
        ("pull_request", "CONTRIBUTOR", 1),
        ("pull_request_target", "OWNER", 0),
        ("pull_request_target", "CONTRIBUTOR", 1),
        ("pull_request_review", "MEMBER", 0),
        ("pull_request_review", "FIRST_TIME_CONTRIBUTOR", 1),
        ("pull_request_review_comment", "COLLABORATOR", 0),
        ("pull_request_review_comment", "NONE", 1),
        ("issue_comment", "OWNER", 0),
        ("issue_comment", "CONTRIBUTOR", 1),
        # Events that skip author association checks
        ("push", "CONTRIBUTOR", 0),  # Should be skipped
        ("workflow_dispatch", "CONTRIBUTOR", 0),  # Should be skipped
        ("schedule", "CONTRIBUTOR", 0),  # Should be skipped
    ],
    ids=[
        "pr_owner_allowed",
        "pr_member_allowed",
        "pr_collaborator_allowed",
        "pr_contributor_blocked",
        "pr_target_owner_allowed",
        "pr_target_contributor_blocked",
        "pr_review_member_allowed",
        "pr_review_first_time_blocked",
        "pr_review_comment_collaborator_allowed",
        "pr_review_comment_none_blocked",
        "issue_comment_owner_allowed",
        "issue_comment_contributor_blocked",
        "push_skipped",
        "workflow_dispatch_skipped",
        "schedule_skipped",
    ],
)
def test_author_association_check_by_event_type(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    event_type: str,
    author_association: str,
    expected_exit_code: int,
    default_template_vars: Dict,
):
    """Test author association checks for different GitHub event types."""
    # Update environment to match the event type
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
    )

    # For PR-related events (except issue_comment), make them fork PRs to test author association logic
    # Internal PRs skip the check, so we need fork PRs to test the actual authorization logic
    if event_type in PR_EVENTS:
        _make_fork_pr(github_event)

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for {event_type} with {author_association}, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    # Check for appropriate log messages
    if event_type in [
        "pull_request",
        "pull_request_target",
        "pull_request_review",
        "pull_request_review_comment",
        "issue_comment",
    ]:
        # These events should trigger the author association check
        assert f"Author association: {author_association}" in result.stderr

        if expected_exit_code == 0:
            assert "The contributor check has passed, proceeding to execute jobs" in result.stderr
            assert "Insufficient user authorization" not in result.stderr
        else:
            assert "Insufficient user authorization (author_association)" in result.stderr
            assert "Only OWNER, MEMBER, or COLLABORATOR may run workflows" in result.stderr
    else:
        # These events should skip the author association check
        assert f"Skipping contributor check for event: {event_type}" in result.stderr
        assert "Author association:" not in result.stderr
        assert "Insufficient user authorization" not in result.stderr


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
    assert f"Skipping contributor check for event: {event_type}" in result.stderr
    assert "Author association:" not in result.stderr
    assert "Insufficient user authorization" not in result.stderr


@pytest.mark.parametrize(
    "author_association,event_type",
    [
        ("CONTRIBUTOR", "pull_request"),
        ("FIRST_TIME_CONTRIBUTOR", "pull_request"),
        ("NONE", "pull_request"),
        ("CONTRIBUTOR", "pull_request_target"),
        ("CONTRIBUTOR", "pull_request_review"),
        ("CONTRIBUTOR", "pull_request_review_comment"),
    ],
    ids=[
        "pr_internal_contributor",
        "pr_internal_first_time",
        "pr_internal_none",
        "pr_target_internal_contributor",
        "pr_review_internal_contributor",
        "pr_review_comment_internal_contributor",
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
    """Test that internal PRs (same repo) skip author association check regardless of role."""
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # Create payload with matching head and base repo (internal PR)
    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
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
    assert "Internal PR detected" in result.stderr
    assert "skipping author association check" in result.stderr
    assert "The contributor check has passed, proceeding to execute jobs" in result.stderr
    # Should NOT perform the author association check
    assert "Author association: " not in result.stderr
    assert "Insufficient user authorization" not in result.stderr


@pytest.mark.parametrize(
    "author_association,expected_exit_code,event_type",
    [
        ("OWNER", 0, "pull_request"),
        ("MEMBER", 0, "pull_request"),
        ("COLLABORATOR", 0, "pull_request"),
        ("CONTRIBUTOR", 1, "pull_request"),
        ("FIRST_TIME_CONTRIBUTOR", 1, "pull_request"),
        ("NONE", 1, "pull_request"),
        ("OWNER", 0, "pull_request_target"),
        ("CONTRIBUTOR", 1, "pull_request_target"),
        ("MEMBER", 0, "pull_request_review"),
        ("CONTRIBUTOR", 1, "pull_request_review"),
        ("COLLABORATOR", 0, "pull_request_review_comment"),
        ("NONE", 1, "pull_request_review_comment"),
    ],
    ids=[
        "fork_pr_owner_allowed",
        "fork_pr_member_allowed",
        "fork_pr_collaborator_allowed",
        "fork_pr_contributor_blocked",
        "fork_pr_first_time_blocked",
        "fork_pr_none_blocked",
        "fork_pr_target_owner_allowed",
        "fork_pr_target_contributor_blocked",
        "fork_pr_review_member_allowed",
        "fork_pr_review_contributor_blocked",
        "fork_pr_review_comment_collaborator_allowed",
        "fork_pr_review_comment_none_blocked",
    ],
)
def test_fork_pr_performs_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    expected_exit_code: int,
    event_type: str,
    default_template_vars: Dict,
):
    """Test that fork PRs (different repos) perform author association check."""
    env_vars = github_env_vars.copy()
    env_vars["GITHUB_EVENT_NAME"] = event_type

    # Create payload with different head and base repo (fork PR)
    github_event = _create_github_event_payload(
        author_association=author_association,
        event_type=event_type,
    )
    # Change head repo to simulate a fork
    _make_fork_pr(github_event)

    result = render_and_execute_script(
        template=pre_job_template,
        template_vars=default_template_vars,
        env_vars=env_vars,
        github_event=github_event,
        tmp_path=tmp_path,
    )

    assert result.returncode == expected_exit_code, (
        f"Expected exit code {expected_exit_code} for fork {event_type} with {author_association}, "
        f"got {result.returncode}\nstderr: {result.stderr}"
    )

    # Should log that it's a fork PR and perform the check
    assert "Fork PR detected" in result.stderr
    assert "performing author association check" in result.stderr
    assert f"Author association: {author_association}" in result.stderr

    if expected_exit_code == 0:
        assert "The contributor check has passed, proceeding to execute jobs" in result.stderr
        assert "Insufficient user authorization" not in result.stderr
    else:
        assert "Insufficient user authorization (author_association)" in result.stderr
        assert "Only OWNER, MEMBER, or COLLABORATOR may run workflows" in result.stderr


@pytest.mark.parametrize(
    "author_association,expected_exit_code,event_type",
    [
        ("OWNER", 0, "pull_request"),
        ("MEMBER", 0, "pull_request"),
        ("COLLABORATOR", 0, "pull_request"),
        ("CONTRIBUTOR", 1, "pull_request"),
        ("OWNER", 0, "pull_request_target"),
        ("CONTRIBUTOR", 1, "pull_request_target"),
    ],
    ids=[
        "missing_repo_owner_allowed",
        "missing_repo_member_allowed",
        "missing_repo_collaborator_allowed",
        "missing_repo_contributor_blocked",
        "missing_repo_target_owner_allowed",
        "missing_repo_target_contributor_blocked",
    ],
)
def test_missing_repo_info_performs_author_association_check(
    pre_job_template: Template,
    github_env_vars: Dict[str, str],
    tmp_path: Path,
    author_association: str,
    expected_exit_code: int,
    event_type: str,
    default_template_vars: Dict,
):
    """Test that missing repo info triggers author association check."""
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

    # Should log that repo info is unavailable and perform the check
    assert "Repository information unavailable" in result.stderr
    assert "performing author association check" in result.stderr
    assert f"Author association: {author_association}" in result.stderr

    if expected_exit_code == 0:
        assert "The contributor check has passed, proceeding to execute jobs" in result.stderr
        assert "Insufficient user authorization" not in result.stderr
    else:
        assert "Insufficient user authorization (author_association)" in result.stderr
        assert "Only OWNER, MEMBER, or COLLABORATOR may run workflows" in result.stderr
