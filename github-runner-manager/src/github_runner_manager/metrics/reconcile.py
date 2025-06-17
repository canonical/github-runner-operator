#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

from prometheus_client import Histogram

RECONCILE_DURATION_SECONDS = Histogram(
    name="reconcile_duration_seconds",
    documentation="Duration of reconciliation (seconds)",
)
