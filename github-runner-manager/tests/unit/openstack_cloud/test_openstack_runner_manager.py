# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for unit-testing OpenStack runner manager."""
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from github_runner_manager.errors import OpenstackHealthCheckError
from github_runner_manager.manager.cloud_runner_manager import SupportServiceConfig
from github_runner_manager.metrics import runner
from github_runner_manager.metrics.storage import MetricsStorage, StorageManager
from github_runner_manager.openstack_cloud import (
    health_checks,
    openstack_cloud,
    openstack_runner_manager,
)
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OUTDATED_METRICS_STORAGE_IN_SECONDS,
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
)
from tests.unit.factories import openstack_factory


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


@pytest.mark.parametrize(
    "healthy_count, unhealthy_count, undecided_count",
    [
        pytest.param(1, 1, 1, id="one of each"),
        pytest.param(2, 1, 1, id="two healthy"),
        pytest.param(1, 2, 1, id="two unhealthy"),
        pytest.param(1, 1, 2, id="two undecided"),
        pytest.param(0, 0, 0, id="no runners"),
        pytest.param(0, 0, 1, id="one undecided"),
        pytest.param(0, 1, 0, id="one unhealthy"),
        pytest.param(1, 0, 0, id="one healthy"),
    ],
)
def test_cleanup_ignores_runners_with_health_check_errors(
    healthy_count: int, unhealthy_count: int, undecided_count: int, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given a combination of healthy/unhealthy/undecided (with a health check error) runners.
    act: When the cleanup method is called.
    assert: Only the unhealthy runners are deleted and got metrics extracted.
    """
    # TODO: Try to see if something can move to a fixture or helper function as this is a lot of setup.

    service_config_mock = MagicMock(spec=SupportServiceConfig)
    service_config_mock.proxy_config = None
    config = OpenStackRunnerManagerConfig(
        name="test",
        prefix="test",
        credentials=MagicMock(),
        server_config=MagicMock(),
        runner_config=MagicMock(),
        service_config=service_config_mock,
        system_user_config=MagicMock(),
    )
    openstack_cloud_mock = MagicMock(spec=openstack_runner_manager.OpenstackCloud)
    names = [
        f"test-{status}{i}"
        for status, count in [
            ("healthy", healthy_count),
            ("unhealthy", unhealthy_count),
            ("undecided", undecided_count),
        ]
        for i in range(count)
    ]
    prefix = "test-"
    openstack_cloud_mock.get_instances.return_value = [
        openstack_cloud.OpenstackInstance(
            server=openstack_factory.ServerFactory(
                status="ACTIVE",
                name=name,
            ),
            prefix="test",
        )
        for name in names
    ]
    health_checks_mock = MagicMock(spec=health_checks)

    def health_checks_side_effect(openstack_cloud, instance):
        if instance.server_name.startswith("test-healthy"):
            return True
        if instance.server_name.startswith("test-unhealthy"):
            return False
        raise OpenstackHealthCheckError("Health check failed")

    health_checks_mock.check_runner.side_effect = health_checks_side_effect
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.OpenstackCloud",
        MagicMock(),
    )
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.metrics_storage",
        MagicMock(),
    )
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.health_checks",
        health_checks_mock,
    )
    runner_manager = OpenStackRunnerManager(config=config)
    runner_manager._openstack_cloud = openstack_cloud_mock

    metric_storage_manager = MagicMock(spec=StorageManager)
    runner_metrics_mock = MagicMock(spec=runner)
    monkeypatch.setattr(openstack_runner_manager, "runner_metrics", runner_metrics_mock)
    now = datetime.now()
    all_runner_name_metrics_storage = [
        _create_metrics_storage(runner_name, now) for runner_name in names
    ]
    metric_storage_manager.list_all = (all_runner_name_metrics_storage).__iter__

    runner_manager.cleanup(secrets.token_hex(16))

    assert openstack_cloud_mock.delete_instance.call_count == unhealthy_count
    for name in names:
        name_without_prefix = name[len(prefix) :]
        if name_without_prefix.startswith("unhealthy"):
            openstack_cloud_mock.delete_instance.assert_any_call(name_without_prefix)

    assert runner_metrics_mock.extract.call_count == 1
    assert runner_metrics_mock.extract.call_args[1]["runners"] == {
        names for names in names if names.startswith("test-unhealthy")
    }


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
