# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Prometheus metrics for GitHub API client calls."""

from prometheus_client import Counter, Gauge, Histogram

from github_runner_manager.metrics import labels

GITHUB_CLIENT_CALLS_TOTAL = Counter(
    name="github_client_calls_total",
    documentation="Total number of GithubClient method calls.",
    labelnames=[labels.METHOD],
)
GITHUB_CLIENT_ERRORS_TOTAL = Counter(
    name="github_client_errors_total",
    documentation="Total number of failed GithubClient method calls.",
    labelnames=[labels.METHOD, labels.ERROR_TYPE],
)
GITHUB_CLIENT_DURATION_SECONDS = Histogram(
    name="github_client_duration_seconds",
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
