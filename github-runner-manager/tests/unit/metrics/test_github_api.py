# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for GitHub API Prometheus metrics."""

import pytest
from github import RateLimitExceededException
from prometheus_client import REGISTRY

from github_runner_manager.metrics.github_api import RateLimiting, record_github_api_metrics
from github_runner_manager.platform.platform_provider import (
    PlatformApiError,
    TokenError,
)


def _sample_value(name: str, labels: dict[str, str] | None = None) -> float:
    """Get a sample value from the default Prometheus registry."""
    value = REGISTRY.get_sample_value(name, labels or {})
    return 0.0 if value is None else value


def _raise_rate_limit_error() -> None:
    """Raise a PlatformApiError with a rate-limit cause."""
    raise PlatformApiError("GitHub API rate limit exceeded.") from RateLimitExceededException(
        403, {}, {}
    )


def _raise_token_error() -> None:
    """Raise TokenError."""
    raise TokenError("Invalid token.")


def _raise_platform_api_error() -> None:
    """Raise PlatformApiError."""
    raise PlatformApiError("unexpected github failure")


def _raise_nested_rate_limit_error() -> None:
    """Raise a PlatformApiError with a nested rate-limit cause chain."""
    try:
        try:
            raise RateLimitExceededException(403, {}, {})
        except RateLimitExceededException as exc:
            raise RuntimeError("intermediate wrapper") from exc
    except RuntimeError as exc:
        raise PlatformApiError("GitHub API rate limit exceeded.") from exc


@pytest.mark.parametrize(
    ("sample_name", "expected_delta"),
    [
        ("github_api_calls_total", 1),
        ("github_api_duration_seconds_count", 1),
    ],
)
def test_successful_call_records_metrics(sample_name: str, expected_delta: int):
    """
    arrange: a callback and initial metric sample value.
    act: record metrics around the callback.
    assert: the selected success metric increases by one.
    """
    labels = {"method": "successful_call"}

    before = _sample_value(sample_name, labels)

    assert (
        record_github_api_metrics(
            method="successful_call",
            get_rate_limiting=lambda: RateLimiting(4999, 5000),
            func=lambda: "ok",
        )
        == "ok"
    )

    after = _sample_value(sample_name, labels)
    assert after - before == pytest.approx(expected_delta)


def test_rate_limit_gauge_updated_from_post_call_value():
    """
    arrange: a callback that updates the latest rate limit state.
    act: record metrics around the callback.
    assert: the global rate limit gauges match the post-call values.
    """
    rate_limiting = RateLimiting(4999, 5000)

    def callback() -> str:
        """Update the rate-limit snapshot during the wrapped call."""
        nonlocal rate_limiting
        rate_limiting = RateLimiting(1234, 5000)
        return "ok"

    record_github_api_metrics(
        method="successful_call",
        get_rate_limiting=lambda: rate_limiting,
        func=callback,
    )

    assert _sample_value("github_api_rate_limit_remaining") == pytest.approx(1234)
    assert _sample_value("github_api_rate_limit_limit") == pytest.approx(5000)


@pytest.mark.parametrize(
    ("method", "error_type", "callback", "expected_exception"),
    [
        ("rate_limit_error", "rate_limit", _raise_rate_limit_error, PlatformApiError),
        (
            "nested_rate_limit_error",
            "rate_limit",
            _raise_nested_rate_limit_error,
            PlatformApiError,
        ),
        ("bad_credentials_error", "token_error", _raise_token_error, TokenError),
        ("github_error", "platform_api_error", _raise_platform_api_error, PlatformApiError),
    ],
)
def test_error_metrics_are_classified(
    method: str,
    error_type: str,
    callback,
    expected_exception: type[Exception],
):
    """
    arrange: a callback that raises a platform-related error.
    act: record metrics around the callback.
    assert: the matching error counter increases by one.
    """
    labels = {"method": method, "error_type": error_type}

    before = _sample_value("github_api_errors_total", labels)

    with pytest.raises(expected_exception):
        record_github_api_metrics(
            method=method,
            get_rate_limiting=lambda: RateLimiting(4999, 5000),
            func=callback,
        )

    after = _sample_value("github_api_errors_total", labels)
    assert after - before == pytest.approx(1)
