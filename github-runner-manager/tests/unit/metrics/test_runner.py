# Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, call

import pytest
from fabric import Connection as SSHConnection
from invoke.runners import Result

from github_runner_manager.errors import IssueMetricEventError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.vm_manager import RunnerMetrics
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.metrics import type as metrics_type
from github_runner_manager.metrics.events import Event
from github_runner_manager.metrics.runner import (
    PulledMetrics,
    PullFileError,
    SSHError,
    _ssh_pull_file,
    pull_runner_metrics,
)
from github_runner_manager.openstack_cloud.constants import (
    POST_JOB_METRICS_FILE_PATH,
    PRE_JOB_METRICS_FILE_PATH,
    RUNNER_INSTALLED_TS_FILE_PATH,
)
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud
from github_runner_manager.types_.github import JobConclusion
from tests.unit.factories.metrics_factory import (
    PostJobMetricsFactory,
    PreJobMetricsFactory,
    PulledMetricsFactory,
    RunnerInstalledFactory,
    RunnerMetricsFactory,
    RunnerStartFactory,
    RunnerStopFactory,
)
from tests.unit.factories.runner_instance_factory import (
    OpenstackInstance,
    OpenstackInstanceFactory,
)


@pytest.fixture(autouse=True, name="issue_event_mock")
def issue_event_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the issue_event function."""
    issue_event_mock = MagicMock()
    monkeypatch.setattr("github_runner_manager.metrics.events.issue_event", issue_event_mock)
    return issue_event_mock


@pytest.fixture(name="runner_fs_base")
def runner_fs_base_fixture(tmp_path: Path) -> Path:
    """Create a runner filesystem base."""
    runner_fs_base = tmp_path / "runner-fs"
    runner_fs_base.mkdir(exist_ok=True)
    return runner_fs_base


def test_pull_runner_metrics_errors(caplog: pytest.LogCaptureFixture):
    """
    arrange: given a mocked cloud service that raises exceptions are different points.
    act: when pull_runner_metrics function is called.
    assert: no metrics are pulled and errors are logged.
    """
    test_instances = []
    get_instance_side_effects: list[None | Exception] = []
    get_ssh_connection_side_effects = []
    # Setup for instance not exists
    test_instances.append(
        (
            not_exists_instance := InstanceID(
                prefix="instance-not-exists", reactive=False, suffix="1"
            )
        )
    )
    get_instance_side_effects.append(None)
    # Setup for instance fail ssh connection
    test_instances.append(
        (fail_ssh_conn_instance := InstanceID(prefix="fail-ssh-conn", reactive=False, suffix="2"))
    )
    fail_ssh_conn_instance_mock = MagicMock()
    fail_ssh_conn_instance_mock.instance_id = fail_ssh_conn_instance
    get_instance_side_effects.append(fail_ssh_conn_instance_mock)
    get_ssh_connection_side_effects.append(SSHError())
    # Setup for instance fail pull file
    test_instances.append(
        (
            fail_pull_file_instance := InstanceID(
                prefix="fail-pull-file", reactive=False, suffix="3"
            )
        )
    )
    fail_pull_file_instance_mock = MagicMock()
    fail_pull_file_instance_mock.instance_id = fail_pull_file_instance
    get_instance_side_effects.append(fail_pull_file_instance_mock)
    ssh_connection_mock = MagicMock()
    ssh_connection_mock.return_value = ssh_connection_mock
    ssh_connection_mock.__enter__ = ssh_connection_mock
    ssh_connection_mock.run.side_effect = [TimeoutError]
    get_ssh_connection_side_effects.append(ssh_connection_mock)
    # Mock cloud service setup
    mock_cloud_service = MagicMock()
    mock_cloud_service.get_instance = MagicMock(side_effect=get_instance_side_effects)
    mock_cloud_service.get_ssh_connection = MagicMock(side_effect=get_ssh_connection_side_effects)

    assert pull_runner_metrics(cloud_service=mock_cloud_service, instance_ids=test_instances) == []
    assert (
        f"Skipping fetching metrics, instance not found: {not_exists_instance}" in caplog.messages
    )
    assert (
        f"Failed to create SSH connection for pulling metrics: {fail_ssh_conn_instance}"
        in caplog.messages
    )
    assert (
        f"Failed to create SSH connection for pulling metrics: {fail_pull_file_instance}"
        in caplog.messages
    )


class FakeOpenStackCloud(OpenstackCloud):
    """Fake OpenStack cloud for testing metrics file pulling."""

    def __init__(
        self,
        initial_instances: list[OpenstackInstance],
        instance_file_contents: list[dict[str, str]],
    ):
        """Initialize the fake OpenStack cloud service.

        Args:
            initial_instances: The instances to initialize the fake with.
            instance_file_contents: Map of instance ID to contents of the metrics file.
        """
        instance_map: dict[InstanceID, OpenstackInstance] = {}
        instance_file_contents_map: dict[InstanceID, dict[str, str]] = {}
        for instance, file_contents_map in zip(initial_instances, instance_file_contents):
            instance_map[instance.instance_id] = instance
            instance_file_contents_map[instance.instance_id] = file_contents_map

        self.instances = {instance.instance_id: instance for instance in initial_instances}
        self.file_contents = instance_file_contents_map

    def get_instance(self, instance_id: InstanceID) -> OpenstackInstance | None:
        """Get an OpenStack instance.

        Args:
            instance_id: The instance ID to fetch.

        Returns:
            The OpenStack instance if exists.
        """
        return self.instances.get(instance_id, None)

    def get_ssh_connection(self, instance: OpenstackInstance) -> MagicMock:
        """Return a fake SSH connection.

        Args:
            instance: The instance to get a fake connection for.

        Returns:
            A mocked connection instance.
        """
        fake_ssh_connection = MagicMock()
        fake_ssh_connection.__enter__.return_value = fake_ssh_connection
        fake_ssh_connection.get = lambda remote, local: local.write(
            bytes(
                self.file_contents.get(instance.instance_id, {}).get(remote, ""), encoding="utf-8"
            )
        )
        return fake_ssh_connection


@pytest.mark.parametrize(
    "instances, instance_metrics_map, expected_metrics",
    [
        pytest.param([], [], [], id="no instances"),
        pytest.param([OpenstackInstanceFactory()], [{}], [], id="single instance, no metrics"),
        pytest.param(
            [instance := OpenstackInstanceFactory()],
            [{str(POST_JOB_METRICS_FILE_PATH): (post_job := PostJobMetricsFactory()).json()}],
            [
                PulledMetricsFactory(
                    instance=instance,
                    runner_installed_timestamp=None,
                    pre_job=None,
                    post_job=post_job,
                )
            ],
            id="single instance, partial metrics(POST_JOB_METRICS_FILE_PATH)",
        ),
        pytest.param(
            [instance := OpenstackInstanceFactory()],
            [{str(PRE_JOB_METRICS_FILE_PATH): (pre_job := PreJobMetricsFactory()).json()}],
            [
                PulledMetricsFactory(
                    instance=instance,
                    runner_installed_timestamp=None,
                    pre_job=pre_job,
                    post_job=None,
                )
            ],
            id="single instance, partial metrics(PRE_JOB_METRICS_FILE_PATH)",
        ),
        pytest.param(
            [instance := OpenstackInstanceFactory()],
            [{str(RUNNER_INSTALLED_TS_FILE_PATH): "1"}],
            [
                PulledMetricsFactory(
                    instance=instance,
                    runner_installed_timestamp=1,
                    pre_job=None,
                    post_job=None,
                )
            ],
            id="single instance, partial metrics(RUNNER_INSTALLED_TS_FILE_PATH)",
        ),
        pytest.param(
            [instance := OpenstackInstanceFactory()],
            [
                {
                    str(POST_JOB_METRICS_FILE_PATH): (post_job := PostJobMetricsFactory()).json(),
                    str(PRE_JOB_METRICS_FILE_PATH): (pre_job := PreJobMetricsFactory()).json(),
                    str(RUNNER_INSTALLED_TS_FILE_PATH): "1",
                }
            ],
            [
                PulledMetricsFactory(
                    instance=instance,
                    runner_installed_timestamp=1,
                    pre_job=pre_job,
                    post_job=post_job,
                )
            ],
            id="single instance, all metrics",
        ),
        pytest.param(
            [instance_1 := OpenstackInstanceFactory(), instance_2 := OpenstackInstanceFactory()],
            [
                {
                    str(POST_JOB_METRICS_FILE_PATH): (
                        post_job_1 := PostJobMetricsFactory()
                    ).json(),
                    str(PRE_JOB_METRICS_FILE_PATH): (pre_job_1 := PreJobMetricsFactory()).json(),
                    str(RUNNER_INSTALLED_TS_FILE_PATH): "1",
                },
                {
                    str(POST_JOB_METRICS_FILE_PATH): (
                        post_job_2 := PostJobMetricsFactory()
                    ).json(),
                    str(PRE_JOB_METRICS_FILE_PATH): (pre_job_2 := PreJobMetricsFactory()).json(),
                    str(RUNNER_INSTALLED_TS_FILE_PATH): "2",
                },
            ],
            [
                PulledMetricsFactory(
                    instance=instance_1,
                    runner_installed_timestamp=1,
                    pre_job=pre_job_1,
                    post_job=post_job_1,
                ),
                PulledMetricsFactory(
                    instance=instance_2,
                    runner_installed_timestamp=2,
                    pre_job=pre_job_2,
                    post_job=post_job_2,
                ),
            ],
            id="multi instance, all metrics",
        ),
    ],
)
def test_pull_runner_metrics(
    instances: list[OpenstackInstance],
    instance_metrics_map: list[dict],
    expected_metrics: list[PulledMetrics],
):
    """
    arrange: given a mock cloud service get_instance method and get_ssh_connection method.
    act: when pull_runner_metrics function is called.
    assert: metrics are pulled from corresponding instances correctly.
    """
    fake_cloud = FakeOpenStackCloud(
        initial_instances=instances, instance_file_contents=instance_metrics_map
    )

    # Compare the set as the order is not guaranteed but it does not matter.
    pulled_metrics = pull_runner_metrics(
        cloud_service=fake_cloud,
        instance_ids=[instance.instance_id for instance in instances],
    )
    assert len(pulled_metrics) == len(
        expected_metrics
    ), f"metrics length mismatch, expected: {expected_metrics}, got: {pulled_metrics}"
    for pulled_metric in pulled_metrics:
        assert pulled_metric in expected_metrics


@pytest.mark.parametrize(
    "metric, flavor, job_metrics, expected_events",
    [
        pytest.param(
            RunnerMetricsFactory(
                pre_job=(test_pre_job := PreJobMetricsFactory(timestamp=1)),
                post_job=None,
                installation_start_timestamp=None,
                installation_end_timestamp=None,
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            [
                RunnerStartFactory(
                    timestamp=test_pre_job.timestamp,
                    flavor=test_flavor,
                    workflow=test_pre_job.workflow,
                    repo=test_pre_job.repository,
                    github_event=test_pre_job.event,
                    queue_duration=test_job_metrics.queue_duration,
                    idle=1,
                )
            ],
            id="runner start (pre-job)",
        ),
        pytest.param(
            test_runner_metrics := RunnerMetricsFactory(
                pre_job=None,
                post_job=None,
                installation_start_timestamp=1,
                installation_end_timestamp=10,
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            [
                RunnerInstalledFactory(
                    timestamp=test_runner_metrics.installation_end_timestamp,
                    flavor=test_flavor,
                    duration=9,
                )
            ],
            id="runner installed (installation timestamps)",
        ),
        pytest.param(
            RunnerMetricsFactory(
                pre_job=None,
                post_job=(test_post_job := PostJobMetricsFactory(timestamp=2)),
                installation_start_timestamp=None,
                installation_end_timestamp=None,
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            [],
            id="runner stop (post job only)",
        ),
        pytest.param(
            RunnerMetricsFactory(
                pre_job=(test_pre_job := PreJobMetricsFactory(timestamp=1)),
                post_job=(test_post_job := PostJobMetricsFactory(timestamp=2)),
                installation_start_timestamp=None,
                installation_end_timestamp=None,
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            [
                RunnerStartFactory(
                    timestamp=test_pre_job.timestamp,
                    flavor=test_flavor,
                    workflow=test_pre_job.workflow,
                    repo=test_pre_job.repository,
                    github_event=test_pre_job.event,
                    queue_duration=test_job_metrics.queue_duration,
                    idle=1,
                ),
                RunnerStopFactory(
                    timestamp=test_post_job.timestamp,
                    flavor=test_flavor,
                    workflow=test_pre_job.workflow,
                    repo=test_pre_job.repository,
                    github_event=test_pre_job.event,
                    status=test_post_job.status,
                    status_info=test_post_job.status_info,
                    job_duration=1,
                    job_conclusion=test_job_metrics.conclusion,
                ),
            ],
            id="runner stop (pre, post job)",
        ),
    ],
)
def test_issue_events(
    metric: RunnerMetrics,
    flavor: str,
    job_metrics: metrics_type.GithubJobMetrics | None,
    expected_events: list[Event],
    issue_event_mock: MagicMock,
):
    """
    arrange: runner metric with abnormal timestamp.
    act: Call issue_events.
    assert: expected events are returned.
    """
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=metric, flavor=flavor, job_metrics=job_metrics
    )

    assert issued_metrics == set(type(event) for event in expected_events)
    issue_event_mock.assert_has_calls([call(event) for event in expected_events], any_order=True)


def _create_metrics_data(instance_id: InstanceID) -> RunnerMetrics:
    """Create a RunnerMetrics object that is suitable for most tests.

    Args:
        instance_id: The test runner name.

    Returns:
        Test metrics data.
    """
    reference_time = datetime.now()
    return PulledMetricsFactory(
        instance=OpenstackInstanceFactory(created_at=reference_time, instance_id=instance_id),
        runner_installed_timestamp=reference_time.timestamp() + 1,
        pre_job=PreJobMetricsFactory(timestamp=reference_time.timestamp() + 2),
        post_job=PostJobMetricsFactory(timestamp=reference_time.timestamp() + 3),
    )


@pytest.mark.parametrize(
    "metric, flavor, job_metrics, expected_event",
    [
        pytest.param(
            test_runner_metrics := RunnerMetricsFactory(
                installation_start_timestamp=1,
                installation_end_timestamp=5,
                pre_job=(test_pre_job := PreJobMetricsFactory(timestamp=1)),
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            RunnerStartFactory(
                timestamp=test_pre_job.timestamp,
                flavor=test_flavor,
                workflow=test_pre_job.workflow,
                repo=test_pre_job.repository,
                github_event=test_pre_job.event,
                queue_duration=test_job_metrics.queue_duration,
                idle=0,
            ),
            id="pre-job timestamp before runner installed timestamp (idle reset)",
        ),
        pytest.param(
            test_runner_metrics := RunnerMetricsFactory(
                pre_job=(test_pre_job := PreJobMetricsFactory(timestamp=5)),
                post_job=(test_post_job := PostJobMetricsFactory(timestamp=1)),
            ),
            test_flavor := "flavor-1",
            test_job_metrics := metrics_type.GithubJobMetrics(
                queue_duration=5, conclusion=metrics_type.JobConclusion.SUCCESS
            ),
            RunnerStopFactory(
                timestamp=test_post_job.timestamp,
                flavor=test_flavor,
                workflow=test_pre_job.workflow,
                repo=test_pre_job.repository,
                github_event=test_pre_job.event,
                status=test_post_job.status,
                status_info=test_post_job.status_info,
                job_duration=0,
                job_conclusion=test_job_metrics.conclusion,
            ),
            id="post-job timestamp before pre-job timestamp (job duration reset)",
        ),
    ],
)
def test_issue_events_correction(
    metric: RunnerMetrics,
    flavor: str,
    job_metrics: metrics_type.GithubJobMetrics | None,
    expected_event: Event,
    issue_event_mock: MagicMock,
):
    """
    arrange: runner metric with abnormal timestamp.
    act: Call issue_events.
    assert: expected events are returned.
    """
    issued_metrics = runner_metrics.issue_events(
        runner_metrics=metric, flavor=flavor, job_metrics=job_metrics
    )

    assert type(expected_event) in issued_metrics
    issue_event_mock.assert_any_call(expected_event)


def test_issue_events_returns_empty_set_on_issue_event_failure(
    issue_event_mock: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: Mock the issue_event_mock to raise an exception on the first call.
    act: Call issue_events.
    assert: No metrics at all are issued. The exception is caught and logged.
    """
    runner_name = InstanceID.build("prefix")
    runner_metrics_data = _create_metrics_data(runner_name)

    issue_event_mock.side_effect = [IssueMetricEventError("Failed to issue metric"), None]

    flavor = secrets.token_hex(16)
    job_metrics = metrics_type.GithubJobMetrics(
        queue_duration=3600, conclusion=JobConclusion.SUCCESS
    )

    issued_metrics = runner_metrics.issue_events(
        runner_metrics=runner_metrics_data, flavor=flavor, job_metrics=job_metrics
    )
    assert not issued_metrics
    assert "Failed to issue metric" in caplog.text


def test_ssh_pull_file():
    """
    arrange: Mock an ssh connection for run and get methods.
       The run expects a stat command that returns a number (file size) and the
       get sends a file through a file-like object.
    act: Call ssh_pull_file.
    assert: The content sent in the mocked ssh get is the same as the one returned by
       ssh_pull_file.
    """
    remote_path = "/var/whatever"
    max_size = 100
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """Expects a stat command for the file and returns a file size."""
        assert "stat" in command
        assert remote_path in command
        file_size = 10
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    def _ssh_get(remote, local) -> None:
        """Mocks get in ssh to write to a file-like object."""
        assert remote_path in remote
        local.write(b"content from")
        local.write(b" the file")
        return None

    ssh_conn.get.side_effect = _ssh_get

    response = _ssh_pull_file(ssh_conn, remote_path, max_size)

    assert response == "content from the file"


def test_ssh_pull_file_invalid_size_real():
    """
    arrange: Mock an ssh connection for run and get methods.
       The run expects a stat command that returns a number (file size) and the
       get sends a file through a file-like object.
    act: Call ssh_pull_file with a limit size smaller than what will be written
       to the file-like object.
    assert: A PullFileError is raised.
    """
    remote_path = "/var/whatever"
    max_size = 10
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """Expects a stat command for the file and returns a file size."""
        assert "stat" in command
        assert remote_path in command
        file_size = 5
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    def _ssh_get(remote, local) -> None:
        """Mocks get in ssh to write to a file-like object."""
        assert remote_path in remote
        local.write(b"content")
        local.write(b"more content")
        return None

    ssh_conn.get.side_effect = _ssh_get

    with pytest.raises(PullFileError) as exc:
        _ = _ssh_pull_file(ssh_conn, remote_path, max_size)
        assert "max" in str(exc)


def test_ssh_pull_file_invalid_size_reported():
    """
    arrange: Mock an ssh connection for run. No need for the get method.
       The run expects a stat command that returns a number (file size).
    act: Call ssh_pull_file with a limit size smaller than what will be return
       by the stat command.
    assert: A PullFileError is raised.
    """
    remote_path = "/var/whatever"
    max_size = 10
    ssh_conn = MagicMock(spec=SSHConnection)

    def _ssh_run(command, **kwargs) -> Optional[Result]:
        """Expects a stat command for the file and returns a file size."""
        assert "stat" in command
        assert remote_path in command
        file_size = 20
        return Result(stdout=str(file_size))

    ssh_conn.run.side_effect = _ssh_run

    with pytest.raises(PullFileError) as exc:
        _ = _ssh_pull_file(ssh_conn, remote_path, max_size)
    assert "too large" in str(exc)
