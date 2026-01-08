#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from storage and issue runner metrics events."""

import concurrent.futures
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Type

import paramiko
import paramiko.ssh_exception
from fabric import Connection as SSHConnection
from prometheus_client import Gauge, Histogram
from pydantic import NonNegativeFloat, ValidationError

from github_runner_manager.errors import IssueMetricEventError, RunnerMetricsError, SSHError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.vm_manager import (
    PostJobMetrics,
    PreJobMetrics,
    RunnerMetadata,
    RunnerMetrics,
)
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics import labels
from github_runner_manager.metrics.type import GithubJobMetrics
from github_runner_manager.openstack_cloud.constants import (
    POST_JOB_METRICS_FILE_PATH,
    PRE_JOB_METRICS_FILE_PATH,
    RUNNER_INSTALLED_TS_FILE_PATH,
)
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud, OpenstackInstance

logger = logging.getLogger(__name__)

MAX_METRICS_FILE_SIZE = 1024
MINUTE_IN_SECONDS = 60
HOURS_IN_SECONDS = MINUTE_IN_SECONDS * 60
DAYS_IN_SECONDS = HOURS_IN_SECONDS * 24

RUNNER_SPAWN_DURATION_SECONDS = Histogram(
    name="runner_spawn_duration_seconds",
    documentation="Time in seconds to initialize the VM and register the runner on GitHub.",
    labelnames=[labels.FLAVOR],
    buckets=[
        5,
        10,
        15,
        30,
        MINUTE_IN_SECONDS,
        MINUTE_IN_SECONDS * 2,
        MINUTE_IN_SECONDS * 3,
        MINUTE_IN_SECONDS * 5,
        MINUTE_IN_SECONDS * 10,
        float("inf"),
    ],
)
RUNNER_IDLE_DURATION_SECONDS = Histogram(
    name="runner_idle_duration_seconds",
    documentation="Time in seconds to runner waiting idle for the job to be picked up.",
    labelnames=[labels.FLAVOR],
    buckets=[
        5,
        10,
        15,
        30,
        MINUTE_IN_SECONDS,
        MINUTE_IN_SECONDS * 2,
        MINUTE_IN_SECONDS * 3,
        MINUTE_IN_SECONDS * 5,
        MINUTE_IN_SECONDS * 10,
        float("inf"),
    ],
)
RUNNER_QUEUE_DURATION_SECONDS = Histogram(
    name="runner_queue_duration_seconds",
    documentation="Time taken in seconds for the job to be started.",
    labelnames=[labels.FLAVOR],
    buckets=[
        # seconds
        5,
        30,
        MINUTE_IN_SECONDS,
        MINUTE_IN_SECONDS * 5,
        MINUTE_IN_SECONDS * 10,
        MINUTE_IN_SECONDS * 20,
        MINUTE_IN_SECONDS * 30,
        HOURS_IN_SECONDS,
        HOURS_IN_SECONDS * 2,
        HOURS_IN_SECONDS * 5,
        float("inf"),
    ],
)
EXTRACT_METRICS_DURATION_SECONDS = Histogram(
    name="extract_metrics_duration_seconds",
    documentation="Time taken in seconds for the metrics to be extracted.",
    labelnames=[labels.FLAVOR],
    buckets=[5, 10, 15, 30, 60, 60 * 2, 60 * 3, 60 * 5, 60 * 10, float("inf")],
)
JOB_DURATION_SECONDS = Histogram(
    name="job_duration_seconds",
    documentation="Time taken in seconds for the job to be completed.",
    labelnames=[labels.FLAVOR],
    buckets=[
        MINUTE_IN_SECONDS,
        MINUTE_IN_SECONDS * 5,
        MINUTE_IN_SECONDS * 10,
        MINUTE_IN_SECONDS * 20,
        MINUTE_IN_SECONDS * 30,
        MINUTE_IN_SECONDS * 60,
        # hours
        HOURS_IN_SECONDS * 2,
        HOURS_IN_SECONDS * 4,
        HOURS_IN_SECONDS * 6,
        # days
        DAYS_IN_SECONDS * 3,
        # Limit of the run is 5 days: https://docs.github.com/en/actions/reference/limits
        DAYS_IN_SECONDS * 5,
        float("inf"),
    ],
)
JOB_REPOSITORY_COUNT = Gauge(
    name="job_repository_count",
    documentation="Number of jobs run per repository.",
    labelnames=[labels.REPOSITORY],
)
JOB_EVENT_COUNT = Gauge(
    name="job_event_count",
    documentation="Number of jobs triggered per event.",
    labelnames=[labels.EVENT],
)
JOB_CONCLUSION_COUNT = Gauge(
    name="job_conclusion_count",
    documentation="Number of jobs per conclusion.",
    labelnames=[labels.CONCLUSION],
)
JOB_STATUS_COUNT = Gauge(
    name="job_status_count", documentation="Number of jobs per status.", labelnames=[labels.STATUS]
)


class PullFileError(Exception):
    """Represents an error while pulling a file from the runner instance."""


@dataclass
class _PullRunnerMetricsConfig:
    """Configurations for pulling runner metrics from a VM.

    Attributes:
        cloud_service: The OpenStack cloud service.
        instance_id: The instance ID to fetch the runner metric from.
    """

    cloud_service: OpenstackCloud
    instance_id: InstanceID


def pull_runner_metrics(
    cloud_service: OpenstackCloud, instance_ids: Sequence[InstanceID]
) -> "list[PulledMetrics]":
    """Pull metrics from runner.

    This function uses multiprocessing to fetch metrics in parallel.

    Args:
        cloud_service: The OpenStack cloud service.
        instance_ids: The instance IDs to fetch the metrics from.

    Returns:
        Metrics pulled from the instance.
    """
    if not instance_ids:
        return []
    pull_metrics_configs = [
        _PullRunnerMetricsConfig(cloud_service=cloud_service, instance_id=instance_id)
        for instance_id in instance_ids
    ]
    pulled_metrics: list[PulledMetrics] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(instance_ids), 30)) as executor:
        future_to_pull_metrics_config = {
            executor.submit(_pull_runner_metrics, config): config
            for config in pull_metrics_configs
        }
        for future in concurrent.futures.as_completed(future_to_pull_metrics_config):
            pull_config = future_to_pull_metrics_config[future]
            metric = future.result()
            if not metric:
                logger.warning("No metrics pulled for %s", pull_config.instance_id)
            else:
                pulled_metrics.append(metric)
    return pulled_metrics


def _pull_runner_metrics(pull_config: _PullRunnerMetricsConfig) -> "PulledMetrics | None":
    """Pull metrics from a single runner via SSH file pull.

    Args:
        pull_config: Configurations for pulling the runner metrics.

    Returns:
        PulledMetrics if metrics were available. None otherwise.
    """
    instance = pull_config.cloud_service.get_instance(instance_id=pull_config.instance_id)
    if not instance:
        logger.warning(
            "Skipping fetching metrics, instance not found: %s", pull_config.instance_id
        )
        return None

    pulled_file_contents = _pull_file_contents(
        cloud_service=pull_config.cloud_service,
        instance=instance,
        metrics_paths=(
            RUNNER_INSTALLED_TS_FILE_PATH,
            PRE_JOB_METRICS_FILE_PATH,
            POST_JOB_METRICS_FILE_PATH,
        ),
    )
    parsed_metrics = _parse_metrics_contents(metrics_contents_map=pulled_file_contents)

    return (
        PulledMetrics(
            instance=instance,
            runner_installed_timestamp=parsed_metrics.runner_installed_timestamp,
            pre_job=parsed_metrics.pre_job_metrics,
            post_job=parsed_metrics.post_job_metrics,
        )
        if (
            parsed_metrics.runner_installed_timestamp
            or parsed_metrics.pre_job_metrics
            or parsed_metrics.post_job_metrics
        )
        else None
    )


def _pull_file_contents(
    cloud_service: OpenstackCloud, instance: OpenstackInstance, metrics_paths: Sequence[Path]
) -> dict[Path, str | None]:
    """Pull the metric files from the runner."""
    metric_files_contents: dict[Path, str | None] = {}
    try:
        with cloud_service.get_ssh_connection(instance=instance) as ssh_conn:
            for remote_path in metrics_paths:
                try:
                    metric_files_contents[remote_path] = _ssh_pull_file(
                        ssh_conn=ssh_conn,
                        remote_path=str(remote_path),
                        max_size=MAX_METRICS_FILE_SIZE,
                    )
                except PullFileError as exc:
                    logger.warning(
                        "Failed to pull file %s metrics for %s: %s.",
                        remote_path.name,
                        instance.instance_id,
                        exc,
                    )
    except SSHError:
        logger.warning(
            "Failed to create SSH connection for pulling metrics: %s", instance.instance_id
        )
    return metric_files_contents


@dataclass
class _ParsedMetricContents:
    """Parsed metric contents mapping.

    Attributes:
        runner_installed_timestamp: The timestamp when the runner was installed.
        pre_job_metrics: Parsed pre-job metrics for the runner.
        post_job_metrics: Parsed post-job metrics for the runner.
    """

    runner_installed_timestamp: float | None
    pre_job_metrics: PreJobMetrics | None
    post_job_metrics: PostJobMetrics | None


def _parse_metrics_contents(metrics_contents_map: dict[Path, str | None]) -> _ParsedMetricContents:
    """Parse metrics contents to concrete data structures.

    Args:
        metrics_contents_map: The map of metric paths to contents.

    Returns:
        The parsed metric contents.
    """
    runner_installed_timestamp: float | None = None
    if timestamp := metrics_contents_map.get(RUNNER_INSTALLED_TS_FILE_PATH, None):
        try:
            runner_installed_timestamp = float(timestamp)
        except ValueError:
            logger.warning("Corrupt runner installed timestamp: %s", timestamp)

    pre_job_metrics: PreJobMetrics | None = None
    if pre_job := metrics_contents_map.get(PRE_JOB_METRICS_FILE_PATH, None):
        try:
            pre_job_metrics = PreJobMetrics.parse_obj(json.loads(pre_job))
        except (json.JSONDecodeError, ValidationError):
            logger.warning("Corrupt pre-job metrics: %s", pre_job)

    post_job_metrics: PostJobMetrics | None = None
    if post_job := metrics_contents_map.get(POST_JOB_METRICS_FILE_PATH, None):
        try:
            post_job_metrics = PostJobMetrics.parse_obj(json.loads(post_job))
        except (json.JSONDecodeError, ValidationError):
            logger.warning("Corrupt post-job metrics %s", post_job)

    return _ParsedMetricContents(
        runner_installed_timestamp=runner_installed_timestamp,
        pre_job_metrics=pre_job_metrics,
        post_job_metrics=post_job_metrics,
    )


def _ssh_pull_file(ssh_conn: SSHConnection, remote_path: str, max_size: int) -> str:
    """Pull file from the runner instance.

    Args:
        ssh_conn: The SSH connection instance.
        remote_path: The file path on the runner instance.
        max_size: If the file is larger than this, it will not be pulled.

    Returns:
        The content of the file as a string

    Raises:
        PullFileError: Unable to pull the file from the runner instance.
        SSHError: Issue with SSH connection.
    """
    try:
        result = ssh_conn.run(f"stat -c %s {remote_path}", warn=True, timeout=60, hide=True)
    except (
        TimeoutError,
        paramiko.ssh_exception.NoValidConnectionsError,
        paramiko.ssh_exception.SSHException,
    ) as exc:
        raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
    if not result.ok:
        logger.warning(
            (
                "Unable to get file size of %s on instance %s, "
                "exit code: %s, stdout: %s, stderr: %s"
            ),
            remote_path,
            ssh_conn.host,
            result.return_code,
            result.stdout,
            result.stderr,
        )
        raise PullFileError(f"Unable to get file size of {remote_path}")

    stdout = result.stdout
    try:
        stdout.strip()
        size = int(stdout)
        if size > max_size:
            raise PullFileError(f"File size of {remote_path} too large {size} > {max_size}")
    except ValueError as exc:
        raise PullFileError(f"Invalid file size for {remote_path}: stdout") from exc

    try:
        file_like_obj = FileLikeLimited(max_size)
        ssh_conn.get(remote=remote_path, local=file_like_obj)
        value = file_like_obj.getvalue().decode("utf-8")
    except (
        TimeoutError,
        paramiko.ssh_exception.NoValidConnectionsError,
        paramiko.ssh_exception.SSHException,
    ) as exc:
        raise SSHError(f"Unable to SSH into {ssh_conn.host}") from exc
    except (OSError, UnicodeDecodeError, FileLimitError) as exc:
        raise PullFileError(f"Error retrieving file {remote_path}. Error: {exc}") from exc
    return value


@dataclass(frozen=True)
class PulledMetrics:
    """Metrics pulled from a runner.

    Attributes:
        instance: The instance in which the metrics were pulled from.
        runner_installed_timestamp: The timestamp in which the runner was installed.
        pre_job: String with the pre-job-metrics file.
        post_job: String with the post-job-metrics file.
        metadata: The metadata of the VM in which the metrics are fetched from.
        instance_id: The instance ID of the VM in which the metrics are fetched from.
        installation_start_timestamp: The UNIX timestamp of in which the VM setup started.
        installation_end_timestamp: The UNIX timestamp of in which the VM setup ended.
    """

    instance: OpenstackInstance
    runner_installed_timestamp: NonNegativeFloat | None = None
    pre_job: PreJobMetrics | None = None
    post_job: PostJobMetrics | None = None

    @property
    def instance_id(self) -> InstanceID:
        """The instance ID of the VM."""
        return self.instance.instance_id

    @property
    def metadata(self) -> RunnerMetadata:
        """The metadata of the VM."""
        return self.instance.metadata

    @property
    def installation_start_timestamp(self) -> NonNegativeFloat:
        """The UNIX timestamp of in which the VM setup started."""
        return self.instance.created_at.timestamp()

    @property
    def installation_end_timestamp(self) -> NonNegativeFloat | None:
        """The UNIX timestamp of in which the VM setup ended."""
        return self.runner_installed_timestamp


def issue_events(
    runner_metrics: RunnerMetrics,
    flavor: str,
    job_metrics: Optional[GithubJobMetrics],
) -> set[Type[metric_events.Event]]:
    """Issue the metrics events for a runner.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Returns:
        A set of issued events.
    """
    issued_events: set[Type[metric_events.Event]] = set()

    try:
        if runner_metrics.installation_start_timestamp:
            issued_events.add(
                _issue_runner_installed(runner_metrics=runner_metrics, flavor=flavor)
            )
        if runner_metrics.pre_job:
            issued_events.add(
                _issue_runner_start(
                    runner_metrics=runner_metrics, flavor=flavor, job_metrics=job_metrics
                )
            )
            if runner_metrics.post_job:
                issued_events.add(
                    _issue_runner_stop(
                        runner_metrics=runner_metrics, flavor=flavor, job_metrics=job_metrics
                    )
                )
        else:
            logger.debug(
                "Pre-job metrics not found for runner %s. Will not issue RunnerStop metric.",
                runner_metrics.instance_id,
            )
    except (ValidationError, IssueMetricEventError):
        if runner_metrics.installation_start_timestamp and not issued_events:
            logger.exception(
                "Not able to issue RunnerInstalled metric for runner %s with"
                " installation_start_timestamp %s."
                "Will not issue RunnerStart and RunnerStop metric.",
                runner_metrics.instance_id,
                runner_metrics.installation_start_timestamp,
            )
        elif metric_events.RunnerStart not in issued_events:
            logger.exception(
                "Not able to issue RunnerStart metric for "
                "runner %s with pre-job metrics %s and job_metrics %s."
                "Will not issue RunnerStop metric.",
                runner_metrics.instance_id,
                runner_metrics.pre_job,
                job_metrics,
            )
        else:
            logger.exception(
                "Not able to issue RunnerStop metric for "
                "runner %s with pre-job metrics %s, post-job metrics %s and job_metrics %s.",
                runner_metrics.instance_id,
                runner_metrics.pre_job,
                runner_metrics.post_job,
                job_metrics,
            )

    return issued_events


def _issue_runner_installed(
    runner_metrics: RunnerMetrics, flavor: str
) -> Type[metric_events.Event]:
    """Issue the RunnerInstalled metric for a runner.

    If installation_end_timestamp is missing for any reasons (SSHError, installation failure, ...),
    the timestamp will be set to the time of metrics issue and duration will be set as infinite.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.

    Returns:
        The type of the issued event.
    """
    installation_end_timestamp = (
        runner_metrics.installation_end_timestamp or datetime.now().timestamp()
    )
    duration = (
        installation_end_timestamp - runner_metrics.installation_start_timestamp
        if runner_metrics.installation_start_timestamp
        else float("inf")
    )
    runner_installed = metric_events.RunnerInstalled(
        timestamp=installation_end_timestamp,
        flavor=flavor,
        duration=duration,
    )
    RUNNER_SPAWN_DURATION_SECONDS.labels(flavor).observe(duration)
    logger.debug("Issuing RunnerInstalled metric for runner %s", runner_metrics.instance_id)
    metric_events.issue_event(runner_installed)

    return metric_events.RunnerInstalled


def _issue_runner_start(
    runner_metrics: RunnerMetrics, flavor: str, job_metrics: Optional[GithubJobMetrics]
) -> Type[metric_events.Event]:
    """Issue the RunnerStart metric for a runner.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Returns:
        The type of the issued event.
    """
    runner_start_event = _create_runner_start(runner_metrics, flavor, job_metrics)

    logger.debug("Issuing RunnerStart metric for runner %s", runner_metrics.instance_id)
    metric_events.issue_event(runner_start_event)
    idle_duration = (
        (runner_metrics.installation_end_timestamp - runner_metrics.pre_job.timestamp)
        if runner_metrics.installation_end_timestamp and runner_metrics.pre_job
        else float("inf")
    )
    RUNNER_IDLE_DURATION_SECONDS.labels(flavor).observe(idle_duration)
    queue_duration = job_metrics.queue_duration if job_metrics else float("inf")
    RUNNER_QUEUE_DURATION_SECONDS.labels(flavor).observe(queue_duration)
    return metric_events.RunnerStart


def _issue_runner_stop(
    runner_metrics: RunnerMetrics, flavor: str, job_metrics: GithubJobMetrics
) -> Type[metric_events.Event]:
    """Issue the RunnerStop metric for a runner.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Returns:
        The type of the issued event.
    """
    runner_stop_event = _create_runner_stop(runner_metrics, flavor, job_metrics)

    logger.debug("Issuing RunnerStop metric for runner %s", runner_metrics.instance_id)
    metric_events.issue_event(runner_stop_event)

    return metric_events.RunnerStop


def _create_runner_start(
    runner_metrics: RunnerMetrics, flavor: str, job_metrics: Optional[GithubJobMetrics]
) -> metric_events.RunnerStart:
    """Create the RunnerStart event.

    Expects that the runner_metrics.pre_job is not None.

    Args:
        runner_metrics: The metrics for the runner containing the pre-job metrics.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Raises:
        RunnerMetricsError: Raised if the pre-job metrics are not found.

    Returns:
        The RunnerStart event.
    """
    if (pre_job_metrics := runner_metrics.pre_job) is None:
        raise RunnerMetricsError(
            "Pre job runner metric not found during RunnerStop event, contact developers"
        )
    # When a job gets picked up directly after spawning, the runner_metrics installed timestamp
    # might be higher than the pre-job timestamp. This is due to the fact that we issue the runner
    # installed timestamp for Openstack after waiting with delays for the runner to be ready.
    # We set the idle_duration to 0 in this case.
    if pre_job_metrics.timestamp < (runner_metrics.installation_end_timestamp or 0):
        logger.warning(
            "Pre-job timestamp %d is before installed timestamp %d for runner %s."
            " Setting idle_duration to zero",
            pre_job_metrics.timestamp,
            runner_metrics.installation_end_timestamp,
            runner_metrics.instance_id,
        )
    idle_duration = max(
        pre_job_metrics.timestamp - (runner_metrics.installation_end_timestamp or 0), 0
    )

    # GitHub API returns started_at < created_at in some rare cases.
    if job_metrics and job_metrics.queue_duration < 0:
        logger.warning(
            "Queue duration for runner %s is negative: %f. Setting it to zero.",
            runner_metrics.instance_id,
            job_metrics.queue_duration,
        )
    queue_duration = max(job_metrics.queue_duration, 0) if job_metrics else None

    return metric_events.RunnerStart(
        timestamp=pre_job_metrics.timestamp,
        flavor=flavor,
        workflow=pre_job_metrics.workflow,
        repo=pre_job_metrics.repository,
        github_event=pre_job_metrics.event,
        idle=idle_duration,
        queue_duration=queue_duration,
    )


def _create_runner_stop(
    runner_metrics: RunnerMetrics, flavor: str, job_metrics: GithubJobMetrics
) -> metric_events.RunnerStop:
    """Create the RunnerStop event.

    Expects that the runner_metrics.pre_job and runner_metrics.post_job is not None.

    Args:
        runner_metrics: The metrics for the runner containing the pre- and post-job metrics.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Raises:
        RunnerMetricsError: Raised if the pre-job or post-job metrics are not found.

    Returns:
        The RunnerStop event.
    """
    if (pre_job_metrics := runner_metrics.pre_job) is None:
        raise RunnerMetricsError(
            "Pre job runner metric not found during RunnerStop event, contact developers"
        )
    if (post_job_metrics := runner_metrics.post_job) is None:
        raise RunnerMetricsError(
            "Post job runner metric not found during RunnerStop event, contact developers"
        )

    # When a job gets cancelled directly after spawning,
    # the post-job timestamp might be lower then the pre-job timestamp.
    # This is due to the fact that we don't have a real post-job script but rather use
    # the exit code of the runner application which might exit before the pre-job script
    # job is done in edge cases. See also:
    # https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/running-scripts-before-or-after-a-job#triggering-the-scripts
    # We set the job_duration to 0 in this case.
    if post_job_metrics.timestamp < pre_job_metrics.timestamp:
        logger.warning(
            "Post-job timestamp %d is before pre-job timestamp %d for runner %s."
            " Setting job_duration to zero",
            post_job_metrics.timestamp,
            pre_job_metrics.timestamp,
            runner_metrics.instance_id,
        )
    job_duration = max(post_job_metrics.timestamp - pre_job_metrics.timestamp, 0)
    JOB_DURATION_SECONDS.labels(flavor).observe(job_duration)
    JOB_REPOSITORY_COUNT.labels(pre_job_metrics.repository).inc()
    JOB_EVENT_COUNT.labels(pre_job_metrics.event).inc()
    JOB_CONCLUSION_COUNT.labels(job_metrics.conclusion if job_metrics else "unknown").inc()
    JOB_STATUS_COUNT.labels(str(post_job_metrics.status)).inc()
    return metric_events.RunnerStop(
        timestamp=post_job_metrics.timestamp,
        flavor=flavor,
        workflow=pre_job_metrics.workflow,
        repo=pre_job_metrics.repository,
        github_event=pre_job_metrics.event,
        status=post_job_metrics.status,
        status_info=post_job_metrics.status_info,
        job_duration=job_duration,
        job_conclusion=job_metrics.conclusion if job_metrics else None,
    )


class FileLimitError(Exception):
    """Error returned when a file is too large."""


class FileLikeLimited(io.BytesIO):
    """file-like object with a maximum possible size."""

    def __init__(self, max_size: int):
        """Create a new FileLikeLimited object.

        Args:
            max_size: Maximum allowed size for the file-like object.
        """
        self.max_size = max_size

    # The type of b is tricky. In Python 3.12 it is a collections.abc.Buffer,
    # and as so it does not have len (we use Python 3.10). For our purpose this works,
    # as Fabric sends bytes. If it ever changes, we will catch it in the
    # integration tests.
    def write(self, b, /) -> int:  # type: ignore[no-untyped-def]
        """Write to the internal buffer for the file-like object.

        Args:
            b: bytes to write.

        Returns:
            Number of bytes written.

        Raises:
            FileLimitError: Raised when what is written to the file is over the allowed size.
        """
        if len(self.getvalue()) + len(b) > self.max_size:
            raise FileLimitError(f"Exceeded allowed max file size {self.max_size})")
        return super().write(b)
