#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

from prometheus_client import Gauge, Histogram

RECONCILE_DURATION_SECONDS = Histogram(
    name="reconcile_duration_seconds",
    documentation="Duration of reconciliation (seconds)",
    labelnames=["flavor"],
)
EXPECTED_RUNNERS_COUNT = Gauge(
    name="expected_runners_count",
    documentation="Expected number of runners",
    labelnames=["flavor"],
)
BUSY_RUNNERS_COUNT = Gauge(
    name="busy_runners_count",
    documentation="Number of busy runners",
    labelnames=["flavor"],
)
IDLE_RUNNERS_COUNT = Gauge(
    name="idle_runners_count",
    documentation="Number of idle runners",
    labelnames=["flavor"],
)
CLEANED_RUNNERS_TOTAL = Gauge(
    name="cleaned_runners_total",
    documentation="Total number of runners cleaned up",
    labelnames=["flavor"],
)
