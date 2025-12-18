#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Utility functions for metrics collection."""

import logging

from prometheus_client import Counter

logger = logging.getLogger(__name__)


def safe_increment_metric(metric: Counter, **labels: str) -> None:
    """Safely increment a Prometheus metric, ignoring any errors.

    Args:
        metric: The Prometheus metric to increment.
        labels: The labels to apply to the metric.
    """
    try:
        metric.labels(**labels).inc()
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to increment Prometheus metric")
