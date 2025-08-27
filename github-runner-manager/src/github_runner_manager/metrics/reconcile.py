#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

from prometheus_client import Counter, Gauge, Histogram

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
DELETED_RUNNERS_TOTAL = Counter(
    name="deleted_runners_total",
    documentation="The number of removed runners from GitHub during reconciliation.",
    labelnames=[labels.FLAVOR],
)
DELETE_RUNNER_DURATION_SECONDS = Histogram(
    name="delete_runner_duration_seconds",
    documentation="Time taken in seconds to remove runners from GitHub.",
    labelnames=[labels.FLAVOR],
)
DELETED_VMS_TOTAL = Counter(
    name="deleted_vms_total",
    documentation="The number of VMs deleted during reconciliation.",
    labelnames=[labels.FLAVOR],
)
DELETE_VM_DURATION_SECONDS = Histogram(
    name="delete_vm_duration_seconds",
    documentation="Time taken in seconds for vms to be deleted.",
    labelnames=[labels.FLAVOR],
)
