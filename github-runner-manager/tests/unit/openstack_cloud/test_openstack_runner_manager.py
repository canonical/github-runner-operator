# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for unit-testing OpenStack runner manager."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from github_runner_manager.metrics import runner
from github_runner_manager.metrics.storage import MetricsStorage, StorageManager
from github_runner_manager.openstack_cloud import openstack_runner_manager
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OUTDATED_METRICS_STORAGE_IN_SECONDS,
    OpenStackRunnerManager,
)


@pytest.mark.parametrize(
    "healthy_runner_names, unhealthy_runner_names, undecided_runner_storage, "
    "expected_storage_to_be_extracted",
    [
        pytest.param(
            default_healthy := {"healthy1", "healthy2"},
            default_unhealthy := {"unhealthy1", "unhealthy2"},
            default_undecided := {
                ("in_construction", datetime.now()),
                (
                    "dangling",
                    datetime.now() - timedelta(seconds=OUTDATED_METRICS_STORAGE_IN_SECONDS + 1),
                ),
            },
            default_result := default_unhealthy | {"dangling"},
            id="one dangling",
        ),
        pytest.param(
            default_healthy,
            default_unhealthy,
            {
                ("in_construction", datetime.now()),
                (
                    "dangling",
                    datetime.now() - timedelta(seconds=OUTDATED_METRICS_STORAGE_IN_SECONDS + 1),
                ),
                (
                    "dangling2",
                    datetime.now() - timedelta(seconds=OUTDATED_METRICS_STORAGE_IN_SECONDS + 1),
                ),
            },
            default_unhealthy | {"dangling", "dangling2"},
            id="two dangling",
        ),
        pytest.param(
            default_healthy,
            default_unhealthy,
            {("in_construction", datetime.now())},
            default_unhealthy,
            id="no dangling",
        ),
        pytest.param(
            default_healthy,
            set(),
            default_undecided,
            {"dangling"},
            id="no unhealthy",
        ),
        pytest.param(
            default_healthy,
            default_unhealthy,
            set(),
            default_unhealthy,
            id="no undecided",
        ),
        pytest.param(
            set(),
            default_unhealthy,
            default_undecided,
            default_result,
            id="no healthy",
        ),
    ],
)
def test__cleanup_extract_metrics(
    healthy_runner_names: set[str],
    unhealthy_runner_names: set[str],
    undecided_runner_storage: set[tuple[str, datetime]],
    expected_storage_to_be_extracted: set[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Given different combinations of healthy, unhealthy and undecided runners.
    act: When the cleanup method is called.
    assert: runner_metrics.extract is called with the expected storage to be extracted.
    """
    metric_storage_manager = MagicMock(spec=StorageManager)
    runner_metrics_mock = MagicMock(spec=runner)
    monkeypatch.setattr(openstack_runner_manager, "runner_metrics", runner_metrics_mock)
    now = datetime.now()
    all_runner_name_metrics_storage = [
        _create_metrics_storage(runner_name, now)
        for runner_name in (healthy_runner_names | unhealthy_runner_names)
    ]
    dangling_runner_metrics_storage = [
        _create_metrics_storage(runner_name, mtime)
        for runner_name, mtime in undecided_runner_storage
    ]
    metric_storage_manager.list_all = (
        all_runner_name_metrics_storage + dangling_runner_metrics_storage
    ).__iter__

    OpenStackRunnerManager._cleanup_extract_metrics(
        metrics_storage_manager=metric_storage_manager,
        healthy_runner_names=healthy_runner_names,
        unhealthy_runner_names=unhealthy_runner_names,
    )

    assert runner_metrics_mock.extract.call_count == 1
    assert runner_metrics_mock.extract.call_args[1]["runners"] == expected_storage_to_be_extracted


def _create_metrics_storage(runner_name: str, mtime: datetime) -> MetricsStorage:
    """
    Create a metric storage object with a mocked mtime for the storage path.

    Args:
        runner_name: The name of the runner.
        mtime: Used to mock the mtime of the storage path.

    Returns:
        A metric storage mock object.
    """
    metrics_storage = MetricsStorage(runner_name=runner_name, path=MagicMock(spec=Path))
    stat = MagicMock()
    stat_mock = MagicMock(return_value=stat)
    stat.st_mtime = mtime.timestamp()
    metrics_storage.path.stat = stat_mock
    return metrics_storage
