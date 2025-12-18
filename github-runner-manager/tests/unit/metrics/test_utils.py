#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Tests for metrics utility functions."""

from unittest.mock import MagicMock, patch

from prometheus_client import Counter

from github_runner_manager.metrics.utils import safe_increment_metric


def test_safe_increment_metric_success():
    """
    arrange: Create a valid Counter metric.
    act: Call safe_increment_metric with valid labels.
    assert: The metric is incremented without raising an exception.
    """
    metric = Counter(
        name="test_metric_success",
        documentation="Test metric",
        labelnames=["label1"],
    )

    safe_increment_metric(metric, label1="value1")

    # Verify the metric was incremented
    assert metric.labels(label1="value1")._value.get() == 1.0


def test_safe_increment_metric_exception():
    """
    arrange: Create a mock Counter that raises an exception when labels() is called.
    act: Call safe_increment_metric.
    assert: The exception is caught and logged, without propagating.
    """
    metric = MagicMock(spec=Counter)
    metric.labels.side_effect = ValueError("Invalid label value")

    # Should not raise an exception
    with patch("github_runner_manager.metrics.utils.logger") as mock_logger:
        safe_increment_metric(metric, endpoint="test_endpoint")

        # Verify that logger.exception was called
        mock_logger.exception.assert_called_once_with("Failed to increment Prometheus metric")


def test_safe_increment_metric_multiple_labels():
    """
    arrange: Create a Counter metric with multiple labels.
    act: Call safe_increment_metric with multiple label values.
    assert: The metric is incremented correctly.
    """
    metric = Counter(
        name="test_metric_multi",
        documentation="Test metric with multiple labels",
        labelnames=["label1", "label2"],
    )

    safe_increment_metric(metric, label1="value1", label2="value2")

    # Verify the metric was incremented
    assert metric.labels(label1="value1", label2="value2")._value.get() == 1.0
