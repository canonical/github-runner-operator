# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Prometheus metrics for GitHub API client calls."""

import functools
from time import perf_counter
from typing import Any, Callable, ParamSpec, TypeVar

from github import RateLimitExceededException
from prometheus_client import Counter, Gauge, Histogram

from github_runner_manager.metrics import labels
from github_runner_manager.platform.platform_provider import (
    PlatformApiError,
    PlatformError,
    TokenError,
)

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")

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


def _update_rate_limit_metrics(requester: Any) -> None:
    """Update rate limit gauges from the PyGithub requester."""
    rate_limiting = getattr(requester, "rate_limiting", None)
    if not isinstance(rate_limiting, tuple) or len(rate_limiting) != 2:
        return
    remaining, limit = rate_limiting
    if remaining is not None:
        GITHUB_API_RATE_LIMIT_REMAINING.set(remaining)
    if limit is not None:
        GITHUB_API_RATE_LIMIT_LIMIT.set(limit)


def _classify_error(exc: Exception) -> str:
    """Map translated GitHub client exceptions to metric label values.

    Checks the exception cause chain for RateLimitExceededException to reliably
    identify rate limit errors regardless of message text.
    """
    if isinstance(exc, TokenError):
        return "token_error"
    cause = exc.__cause__
    if isinstance(cause, RateLimitExceededException):
        return "rate_limit"
    if isinstance(exc, PlatformApiError):
        return "platform_api_error"
    return type(exc).__name__


def record_github_api_metrics(method: str, requester: Any, func: Callable[[], ReturnT]) -> ReturnT:
    """Record GitHub API metrics around a callback.

    Args:
        method: Method name to use for the Prometheus label.
        requester: PyGithub requester used to read rate limit state.
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
        _update_rate_limit_metrics(requester)


def track_github_api_metrics(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
    """Track call count, errors, duration, and rate limit state for GitHub client methods.

    Args:
        func: GithubClient method to instrument.

    Returns:
        A wrapped method that emits GitHub API metrics.
    """

    @functools.wraps(func)
    def wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        """Wrap the target method with GitHub API metric collection.

        Args:
            args: Positional arguments for the wrapped method.
            kwargs: Keyword arguments for the wrapped method.

        Returns:
            The wrapped method result.
        """
        requester = getattr(args[0], "_requester", None) if args else None
        return record_github_api_metrics(
            method=func.__name__,
            requester=requester,
            func=lambda: func(*args, **kwargs),
        )

    return wrapper
