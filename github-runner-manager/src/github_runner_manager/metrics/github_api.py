# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Prometheus metrics for GitHub API client calls."""

from time import perf_counter
from typing import Callable, NamedTuple, TypeVar

from github import RateLimitExceededException
from prometheus_client import Counter, Gauge, Histogram

from github_runner_manager.metrics import labels
from github_runner_manager.platform.platform_provider import (
    PlatformApiError,
    PlatformError,
    TokenError,
)

ReturnT = TypeVar("ReturnT")


class RateLimiting(NamedTuple):
    """GitHub API rate-limit snapshot.

    Attributes:
        remaining: Remaining requests in the current rate-limit window.
        limit: Total requests allowed in the current rate-limit window.
    """

    remaining: int
    limit: int


GITHUB_API_CALLS_TOTAL = Counter(
    name="github_api_calls_total",
    documentation="Total number of GithubClient method calls.",
    labelnames=[labels.METHOD],
)
GITHUB_API_ERRORS_TOTAL = Counter(
    name="github_api_errors_total",
    documentation="Total number of failed GithubClient method calls.",
    labelnames=[labels.METHOD, labels.ERROR_TYPE],
)
GITHUB_API_DURATION_SECONDS = Histogram(
    name="github_api_duration_seconds",
    documentation="Time taken in seconds for GithubClient method calls.",
    labelnames=[labels.METHOD],
)
GITHUB_API_RATE_LIMIT_REMAINING = Gauge(
    name="github_api_rate_limit_remaining",
    documentation="Remaining GitHub API rate limit from the most recent response.",
)
GITHUB_API_RATE_LIMIT_LIMIT = Gauge(
    name="github_api_rate_limit_limit",
    documentation="GitHub API rate limit from the most recent response.",
)


def record_github_api_metrics(
    method: str, get_rate_limiting: Callable[[], RateLimiting], func: Callable[[], ReturnT]
) -> ReturnT:
    """Record GitHub API metrics around a callback.

    Args:
        method: Method name to use for the Prometheus label.
        get_rate_limiting: Callback returning the most recent GitHub API rate-limit snapshot.
        func: Callback that executes the GitHub API operation.

    Raises:
        PlatformError: Re-raised after recording error metrics.

    Returns:
        The callback result.
    """
    start = perf_counter()
    try:
        return func()
    except PlatformError as exc:
        GITHUB_API_ERRORS_TOTAL.labels(method=method, error_type=_classify_error(exc)).inc()
        raise
    finally:
        GITHUB_API_CALLS_TOTAL.labels(method=method).inc()
        GITHUB_API_DURATION_SECONDS.labels(method=method).observe(perf_counter() - start)
        rate_limiting = get_rate_limiting()
        GITHUB_API_RATE_LIMIT_REMAINING.set(rate_limiting.remaining)
        GITHUB_API_RATE_LIMIT_LIMIT.set(rate_limiting.limit)


def _classify_error(exc: Exception) -> str:
    """Map translated GitHub client exceptions to metric label values.

    Checks the exception cause chain for RateLimitExceededException to reliably
    identify rate limit errors regardless of message text.
    """
    if isinstance(exc, TokenError):
        return "token_error"
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, RateLimitExceededException):
            return "rate_limit"
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    if isinstance(exc, PlatformApiError):
        return "platform_api_error"
    return "other"
