#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from storage and issue runner metrics events."""

import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError
from typing import Optional, Type

import paramiko
import paramiko.ssh_exception
from fabric import Connection as SSHConnection
from pydantic import ValidationError

from github_runner_manager.errors import IssueMetricEventError, RunnerMetricsError, SSHError
from github_runner_manager.manager.cloud_runner_manager import (
    CloudRunnerInstance,
    PostJobMetrics,
    PreJobMetrics,
    RunnerMetrics,
)
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics.type import GithubJobMetrics
from github_runner_manager.openstack_cloud.constants import (
    POST_JOB_METRICS_FILE_NAME,
    PRE_JOB_METRICS_FILE_NAME,
    RUNNER_INSTALLED_TS_FILE_NAME,
)

logger = logging.getLogger(__name__)

MAX_METRICS_FILE_SIZE = 1024


class PullFileError(Exception):
    """Represents an error while pulling a file from the runner instance."""


def pull_runner_metrics(instance_id: InstanceID, ssh_conn: SSHConnection) -> "PulledMetrics":
    """Pull metrics from runner.

    Args:
        instance_id: The name of the runner.
        ssh_conn: The SSH connection to the runner.

    Returns:
        Metrics pulled from the instance.
    """
    logger.debug("Pulling metrics for %s", instance_id)
    pulled_metrics = PulledMetrics()

    try:
        pulled_metrics.runner_installed = ssh_pull_file(
            ssh_conn=ssh_conn,
            remote_path=str(RUNNER_INSTALLED_TS_FILE_NAME),
            max_size=MAX_METRICS_FILE_SIZE,
        )
        pulled_metrics.pre_job_metrics = ssh_pull_file(
            ssh_conn=ssh_conn,
            remote_path=str(PRE_JOB_METRICS_FILE_NAME),
            max_size=MAX_METRICS_FILE_SIZE,
        )
        pulled_metrics.post_job_metrics = ssh_pull_file(
            ssh_conn=ssh_conn,
            remote_path=str(POST_JOB_METRICS_FILE_NAME),
            max_size=MAX_METRICS_FILE_SIZE,
        )
    except PullFileError as exc:
        logger.warning(
            "Failed to pull metrics for %s: %s . Will not be able to issue all metrics",
            instance_id,
            exc,
        )
    return pulled_metrics


def ssh_pull_file(ssh_conn: SSHConnection, remote_path: str, max_size: int) -> str:
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


@dataclass
class PulledMetrics:
    """Metrics pulled from a runner.

    Attributes:
        runner_installed: String with the runner-installed file.
        pre_job_metrics: String with the pre-job-metrics file.
        post_job_metrics: String with the post-job-metrics file.
    """

    runner_installed: str | None = None
    pre_job_metrics: str | None = None
    post_job_metrics: str | None = None

    def to_runner_metrics(
        self, instance: CloudRunnerInstance, installation_start: datetime
    ) -> RunnerMetrics | None:
        """.

        Args:
           instance: Cloud runner instance.
           installation_start: Creation time of the runner.

        Returns:
           The RunnerMetrics object for the runner or None if it can not be built.
        """
        instance_id = instance.instance_id
        if self.runner_installed is None:
            logger.error(
                "Invalid pulled metrics. No runner_installed information for %s.", instance_id
            )
            return None

        pre_job_metrics: dict | None = None
        post_job_metrics: dict | None = None
        try:
            pre_job_metrics = json.loads(self.pre_job_metrics) if self.pre_job_metrics else None
            post_job_metrics = json.loads(self.post_job_metrics) if self.post_job_metrics else None
        except (JSONDecodeError, TypeError):
            logger.exception(
                "Json Decode error. Corrupt metric data found for runner %s", instance_id
            )

        if not (pre_job_metrics is None or isinstance(pre_job_metrics, dict)):
            logger.error(
                "Pre job metrics for runner %s %s are not correct. Value: %s",
                instance_id,
                self,
                pre_job_metrics,
            )
            pre_job_metrics = None

        if not (post_job_metrics is None or isinstance(post_job_metrics, dict)):
            logger.error(
                "Post job metrics for runner %s %s are not correct. Value: %s",
                instance_id,
                self,
                post_job_metrics,
            )
            post_job_metrics = None

        try:
            return RunnerMetrics(
                installation_start_timestamp=installation_start.timestamp(),
                installed_timestamp=float(self.runner_installed),
                pre_job=(  # pylint: disable=not-a-mapping
                    PreJobMetrics(**pre_job_metrics) if pre_job_metrics else None
                ),
                post_job=(  # pylint: disable=not-a-mapping
                    PostJobMetrics(**post_job_metrics) if post_job_metrics else None
                ),
                instance_id=instance_id,
                metadata=instance.metadata,
            )
        except ValueError:
            logger.exception(
                "Error creating RunnerMetrics %s, %s, %s", instance_id, installation_start, self
            )
            return None


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

    Assumes that the runner installed timestamp is present.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.

    Returns:
        The type of the issued event.
    """
    runner_installed = metric_events.RunnerInstalled(
        timestamp=runner_metrics.installed_timestamp,
        flavor=flavor,
        # the installation_start_timestamp should be present
        duration=runner_metrics.installed_timestamp  # type: ignore
        - runner_metrics.installation_start_timestamp,  # type: ignore
    )
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
    if pre_job_metrics.timestamp < runner_metrics.installed_timestamp:
        logger.warning(
            "Pre-job timestamp %d is before installed timestamp %d for runner %s."
            " Setting idle_duration to zero",
            pre_job_metrics.timestamp,
            runner_metrics.installed_timestamp,
            runner_metrics.instance_id,
        )
    idle_duration = max(pre_job_metrics.timestamp - runner_metrics.installed_timestamp, 0)

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
