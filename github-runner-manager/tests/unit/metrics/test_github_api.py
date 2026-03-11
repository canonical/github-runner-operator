# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for GitHub API Prometheus metrics."""

from unittest.mock import MagicMock

import pytest
from github import GithubException, RateLimitExceededException
from prometheus_client import REGISTRY

from github_runner_manager.configuration.github import GitHubRepo
from github_runner_manager.github_client import GithubClient
from github_runner_manager.metrics.github_api import track_github_api_metrics
from github_runner_manager.platform.platform_provider import (
    JobNotFoundError,
    PlatformApiError,
    TokenError,
)


def _sample_value(name: str, labels: dict[str, str] | None = None) -> float:
    """Get a sample value from the default Prometheus registry."""
    value = REGISTRY.get_sample_value(name, labels or {})
    return 0.0 if value is None else value


class _DummyGitHubClient:
    """Test helper exposing the GitHub API metrics decorator."""

    def __init__(self):
        """Create a dummy requester with default rate limit state."""
        self._requester = MagicMock()
        self._requester.rate_limiting = (4999, 5000)

    @track_github_api_metrics
    def successful_call(self) -> str:
        """Return a successful result."""
        return "ok"

    @track_github_api_metrics
    def rate_limit_error(self) -> None:
        """Raise a translated rate limit error with a chained cause."""
        raise PlatformApiError("GitHub API rate limit exceeded.") from RateLimitExceededException(
            403, {}, {}
        )

    @track_github_api_metrics
    def bad_credentials_error(self) -> None:
        """Raise a translated token error."""
        raise TokenError("Invalid token.")

    @track_github_api_metrics
    def github_error(self) -> None:
        """Raise a translated generic platform API error."""
        raise PlatformApiError("unexpected github failure")


def test_successful_call_increments_counter():
    """
    arrange: a dummy GitHub client with a decorated method.
    act: call the method.
    assert: the method counter increases by one.
    """
    client = _DummyGitHubClient()
    labels = {"method": "successful_call"}

    before = _sample_value("github_api_calls_total", labels)

    assert client.successful_call() == "ok"

    after = _sample_value("github_api_calls_total", labels)
    assert after - before == pytest.approx(1)


def test_successful_call_observes_duration():
    """
    arrange: a dummy GitHub client with a decorated method.
    act: call the method.
    assert: the histogram count increases by one.
    """
    client = _DummyGitHubClient()
    labels = {"method": "successful_call"}

    before = _sample_value("github_api_duration_seconds_count", labels)

    client.successful_call()

    after = _sample_value("github_api_duration_seconds_count", labels)
    assert after - before == pytest.approx(1)


def test_rate_limit_gauge_updated():
    """
    arrange: a dummy GitHub client with requester rate limit data.
    act: call the method.
    assert: the global rate limit gauges match the requester's current values.
    """
    client = _DummyGitHubClient()
    client._requester.rate_limiting = (1234, 5000)

    client.successful_call()

    assert _sample_value("github_api_rate_limit_remaining") == pytest.approx(1234)
    assert _sample_value("github_api_rate_limit_limit") == pytest.approx(5000)


def test_rate_limit_error():
    """
    arrange: a decorated method that raises a translated rate limit error.
    act: call the method.
    assert: the rate_limit error counter increases by one.
    """
    client = _DummyGitHubClient()
    labels = {"method": "rate_limit_error", "error_type": "rate_limit"}

    before = _sample_value("github_api_errors_total", labels)

    with pytest.raises(PlatformApiError):
        client.rate_limit_error()

    after = _sample_value("github_api_errors_total", labels)
    assert after - before == pytest.approx(1)


def test_bad_credentials_error():
    """
    arrange: a decorated method that raises TokenError.
    act: call the method.
    assert: the token_error counter increases by one.
    """
    client = _DummyGitHubClient()
    labels = {"method": "bad_credentials_error", "error_type": "token_error"}

    before = _sample_value("github_api_errors_total", labels)

    with pytest.raises(TokenError):
        client.bad_credentials_error()

    after = _sample_value("github_api_errors_total", labels)
    assert after - before == pytest.approx(1)


def test_github_error():
    """
    arrange: a decorated method that raises PlatformApiError.
    act: call the method.
    assert: the platform_api_error counter increases by one.
    """
    client = _DummyGitHubClient()
    labels = {"method": "github_error", "error_type": "platform_api_error"}

    before = _sample_value("github_api_errors_total", labels)

    with pytest.raises(PlatformApiError):
        client.github_error()

    after = _sample_value("github_api_errors_total", labels)
    assert after - before == pytest.approx(1)


def test_get_job_info_by_runner_name_tracks_metrics(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: a GithubClient with a mocked requester returning a matching job.
    act: fetch the job information by runner name.
    assert: the method call and duration metrics are recorded.
    """
    client = GithubClient(token="test-token")
    requester = MagicMock()
    requester.rate_limiting = (4321, 5000)
    requester.requestJsonAndCheck.return_value = (
        {},
        {
            "jobs": [
                {
                    "id": 1,
                    "runner_name": "runner-1",
                    "created_at": "2026-03-10T09:00:00Z",
                    "started_at": "2026-03-10T09:01:00Z",
                    "conclusion": "success",
                    "status": "completed",
                }
            ]
        },
    )
    monkeypatch.setattr(client, "_requester", requester)

    call_labels = {"method": "get_job_info_by_runner_name"}
    before_calls = _sample_value("github_api_calls_total", call_labels)
    before_duration = _sample_value("github_api_duration_seconds_count", call_labels)

    job_info = client.get_job_info_by_runner_name(
        path=GitHubRepo(owner="owner", repo="repo"),
        workflow_run_id="123",
        runner_name="runner-1",
    )

    assert job_info.job_id == 1
    assert _sample_value("github_api_calls_total", call_labels) - before_calls == pytest.approx(1)
    assert _sample_value("github_api_duration_seconds_count", call_labels) - before_duration == (
        pytest.approx(1)
    )
    assert _sample_value("github_api_rate_limit_remaining") == pytest.approx(4321)


def test_get_job_info_by_runner_name_token_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: a GithubClient requester that raises an auth-related GithubException.
    act: fetch the job information by runner name.
    assert: the token_error counter increases by one.
    """
    client = GithubClient(token="test-token")
    requester = MagicMock()
    requester.rate_limiting = (4000, 5000)
    requester.requestJsonAndCheck.side_effect = GithubException(status=401, data={})
    monkeypatch.setattr(client, "_requester", requester)
    labels = {"method": "get_job_info_by_runner_name", "error_type": "token_error"}
    before = _sample_value("github_api_errors_total", labels)

    with pytest.raises(TokenError):
        client.get_job_info_by_runner_name(
            path=GitHubRepo(owner="owner", repo="repo"),
            workflow_run_id="123",
            runner_name="runner-1",
        )

    after = _sample_value("github_api_errors_total", labels)
    assert after - before == pytest.approx(1)


def test_get_job_info_by_runner_name_job_not_found(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: a GithubClient requester that returns no matching runner.
    act: fetch the job information by runner name.
    assert: the JobNotFoundError counter increases by one.
    """
    client = GithubClient(token="test-token")
    requester = MagicMock()
    requester.rate_limiting = (4000, 5000)
    requester.requestJsonAndCheck.return_value = (
        {},
        {"jobs": [{"runner_name": "other-runner"}]},
    )
    monkeypatch.setattr(client, "_requester", requester)
    error_labels = {
        "method": "get_job_info_by_runner_name",
        "error_type": "JobNotFoundError",
    }
    before = _sample_value("github_api_errors_total", error_labels)

    with pytest.raises(JobNotFoundError):
        client.get_job_info_by_runner_name(
            path=GitHubRepo(owner="owner", repo="repo"),
            workflow_run_id="123",
            runner_name="runner-1",
        )

    after = _sample_value("github_api_errors_total", error_labels)
    assert after - before == pytest.approx(1)
