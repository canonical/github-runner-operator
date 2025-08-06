#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

from prometheus_client import Gauge, Histogram

from github_runner_manager.metrics import labels

RECONCILE_DURATION_SECONDS = Histogram(
    name="reconcile_duration_seconds",
    documentation="Duration of reconciliation (seconds)",
    labelnames=[labels.FLAVOR],
    buckets=[60, 2 * 60, 5 * 60, 10 * 60, 15 * 60, float("inf")],
)
EXPECTED_RUNNERS_COUNT = Gauge(
    name="expected_runners_count",
    documentation="Expected number of runners",
    labelnames=[labels.FLAVOR],
)
BUSY_RUNNERS_COUNT = Gauge(
    name="busy_runners_count",
    documentation="Number of busy runners",
    labelnames=[labels.FLAVOR],
)
IDLE_RUNNERS_COUNT = Gauge(
    name="idle_runners_count",
    documentation="Number of idle runners",
    labelnames=[labels.FLAVOR],
)
CLEANED_RUNNERS_TOTAL = Gauge(
    name="cleaned_runners_total",
    documentation="Total number of runners cleaned up",
    labelnames=[labels.FLAVOR],
)
