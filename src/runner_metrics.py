# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from a shared filesystem."""

import json
import logging
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, Type, Iterator

from pydantic import BaseModel, Field, NonNegativeFloat, ValidationError

import metrics
import shared_fs
from errors import CorruptMetricDataError, DeleteSharedFilesystemError, IssueMetricEventError
from metrics_common.storage import StorageManager as MetricsStorageManager, MetricsStorage
from metrics_type import GithubJobMetrics

logger = logging.getLogger(__name__)

FILE_SIZE_BYTES_LIMIT = 1024
PRE_JOB_METRICS_FILE_NAME = "pre-job-metrics.json"
POST_JOB_METRICS_FILE_NAME = "post-job-metrics.json"
RUNNER_INSTALLED_TS_FILE_NAME = "runner-installed.timestamp"


class PreJobMetrics(BaseModel):
    """Metrics for the pre-job phase of a runner.

    Attributes:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        workflow: The workflow name.
        workflow_run_id: The workflow run id.
        repository: The repository path in the format '<owner>/<repo>'.
        event: The github event.
    """

    timestamp: NonNegativeFloat
    workflow: str
    workflow_run_id: str
    repository: str = Field(None, regex=r"^.+/.+$")
    event: str


class PostJobStatus(str, Enum):
    """The status of the post-job phase of a runner.

    Attributes:
        NORMAL: Represents a normal post-job.
        ABNORMAL: Represents an error with post-job.
        REPO_POLICY_CHECK_FAILURE: Represents an error with repo-policy-compliance check.
    """

    NORMAL = "normal"
    ABNORMAL = "abnormal"
    REPO_POLICY_CHECK_FAILURE = "repo-policy-check-failure"


class CodeInformation(BaseModel):
    """Information about a status code.

    Attributes:
        code: The status code.
    """

    code: int


class PostJobMetrics(BaseModel):
    """Metrics for the post-job phase of a runner.

    Attributes:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        status: The status of the job.
        status_info: More information about the status.
    """

    timestamp: NonNegativeFloat
    status: PostJobStatus
    status_info: Optional[CodeInformation]


class RunnerMetrics(BaseModel):
    """Metrics for a runner.

    Attributes:
        installed_timestamp: The UNIX time stamp of the time at which the runner was installed.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
        runner_name: The name of the runner.
    """

    installed_timestamp: NonNegativeFloat
    pre_job: PreJobMetrics
    post_job: Optional[PostJobMetrics]
    runner_name: str


def _inspect_file_sizes(metrics_storage: MetricsStorage) -> tuple[Path, ...]:
    """Inspect the file sizes of the shared filesystem.

    Args:
        metrics_storage: The shared filesystem for a specific runner.

    Returns:
        A tuple of files whose size is larger than the limit.
    """
    files: list[Path] = [
        metrics_storage.path.joinpath(PRE_JOB_METRICS_FILE_NAME),
        metrics_storage.path.joinpath(POST_JOB_METRICS_FILE_NAME),
        metrics_storage.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME),
    ]

    return tuple(
        filter(lambda file: file.exists() and file.stat().st_size > FILE_SIZE_BYTES_LIMIT, files)
    )


def _extract_metrics_from_fs_file(
    metrics_storage: MetricsStorage, runner_name: str, filename: str
) -> dict | None:
    """Extract metrics from a shared filesystem.

    Args:
        metrics_storage: The shared filesystem for a specific runner.
        runner_name: The name of the lxd runner to extract metrics from.
        filename: The metrics filename.

    Raises:
        CorruptMetricDataError: If any errors have been found within the metric.

    Returns:
        Metrics for the given runner if present.
    """
    try:
        job_metrics = json.loads(metrics_storage.path.joinpath(filename).read_text())
    except FileNotFoundError:
        logger.warning("%s not found for runner %s.", filename, runner_name)
        return None
    except JSONDecodeError as exc:
        raise CorruptMetricDataError(str(exc)) from exc
    if not isinstance(job_metrics, dict):
        raise CorruptMetricDataError(
            f"{filename} metrics for runner {runner_name} is not a JSON object."
        )
    return job_metrics


def _extract_metrics_from_fs(metrics_storage: MetricsStorage) -> Optional[RunnerMetrics]:
    """Extract metrics from a shared filesystem.

    Args:
        metrics_storage: The shared filesystem for a specific runner.

    Returns:
        The extracted metrics if at least the pre-job metrics are present.

    Raises:
        CorruptMetricDataError: Raised if one of the files is not valid or too large.
    """
    if too_large_files := _inspect_file_sizes(metrics_storage):
        raise CorruptMetricDataError(
            f"File size of {too_large_files} is too large. "
            f"The limit is {FILE_SIZE_BYTES_LIMIT} bytes."
        )

    runner_name = metrics_storage.runner_name
    try:
        installed_timestamp = metrics_storage.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).read_text()
        logger.debug("Runner %s installed at %s", runner_name, installed_timestamp)
    except FileNotFoundError:
        logger.exception("installed_timestamp not found for runner %s", runner_name)
        return None

    try:
        pre_job_metrics = _extract_metrics_from_fs_file(
            metrics_storage=metrics_storage, runner_name=runner_name, filename=PRE_JOB_METRICS_FILE_NAME
        )
        if not pre_job_metrics:
            return None
        logger.debug("Pre-job metrics for runner %s: %s", runner_name, pre_job_metrics)

        post_job_metrics = _extract_metrics_from_fs_file(
            metrics_storage=metrics_storage, runner_name=runner_name, filename=POST_JOB_METRICS_FILE_NAME
        )
        logger.debug("Post-job metrics for runner %s: %s", runner_name, post_job_metrics)
    # 2024/04/02 - We should define a new error, wrap it and re-raise it.
    except CorruptMetricDataError:  # pylint: disable=try-except-raise
        raise

    try:
        return RunnerMetrics(
            installed_timestamp=installed_timestamp,
            pre_job=PreJobMetrics(**pre_job_metrics),
            post_job=PostJobMetrics(**post_job_metrics) if post_job_metrics else None,
            runner_name=runner_name,
        )
    except ValidationError as exc:
        raise CorruptMetricDataError(str(exc)) from exc


def _clean_up_shared_fs(metrics_storage_manager: MetricsStorageManager, metrics_storage: MetricsStorage) -> None:
    """Clean up the shared filesystem.

    Remove all metric files and afterwards the shared filesystem.

    Args:
        metrics_storage_manager: The metrics storage manager.
        metrics_storage: The shared filesystem for a specific runner.
    """
    try:
        metrics_storage.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).unlink(missing_ok=True)
        metrics_storage.path.joinpath(PRE_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
        metrics_storage.path.joinpath(POST_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
    except OSError:
        logger.exception(
            "Could not remove metric files for runner %s, "
            "this may lead to duplicate metrics issued",
            metrics_storage.runner_name,
        )

    try:
        metrics_storage_manager.delete(metrics_storage.runner_name)
    except DeleteSharedFilesystemError:
        logger.exception("Could not delete shared filesystem for runner %s.", metrics_storage.runner_name)


def _extract_fs(
    metrics_storage_manager: MetricsStorageManager,
    metrics_storage: MetricsStorage,
) -> Optional[RunnerMetrics]:
    """Extract metrics from a shared filesystem.

    Args:
        metrics_storage_manager: The metrics storage manager.
        metrics_storage: The metrics storage for a specific runner.

    Returns:
        The extracted metrics if at least the pre-job metrics are present.
    """
    runner_name = metrics_storage.runner_name
    try:
        logger.debug("Extracting metrics from shared filesystem for runner %s", runner_name)
        metrics_from_fs = _extract_metrics_from_fs(metrics_storage)
    except CorruptMetricDataError:
        logger.exception("Corrupt metric data found for runner %s", runner_name)
        metrics_storage_manager.move_to_quarantine(runner_name)
        return None

    logger.debug("Cleaning up shared filesystem for runner %s", runner_name)
    _clean_up_shared_fs(metrics_storage_manager=metrics_storage_manager, metrics_storage=metrics_storage)
    return metrics_from_fs


def extract(metrics_storage_manager: MetricsStorageManager, ignore_runners: set[str]) -> Iterator[RunnerMetrics]:
    """Extract metrics from runners.

    The metrics are extracted from the shared filesystems of the runners.
    Orphan shared filesystems are cleaned up.

    If corrupt data is found, the metrics are not processed further and the filesystem is moved
    to a special quarantine directory, as this may indicate that a malicious
    runner is trying to manipulate the shared file system.

    In order to avoid DoS attacks, the file size is also checked.

    Args:
        metrics_storage_manager: The metrics storage manager.
        ignore_runners: The set of runners to ignore.

    Yields:
        Extracted runner metrics of a particular runner.
    """
    for ms in metrics_storage_manager.list_all():
        if ms.runner_name not in ignore_runners:
            runner_metrics = _extract_fs(metrics_storage_manager=metrics_storage_manager, metrics_storage=ms)
            if not runner_metrics:
                logger.warning("Not able to issue metrics for runner %s", ms.runner_name)
            else:
                yield runner_metrics


def issue_events(
    runner_metrics: RunnerMetrics,
    flavor: str,
    job_metrics: Optional[GithubJobMetrics],
) -> set[Type[metrics.Event]]:
    """Issue the metrics events for a runner.

    Args:
        runner_metrics: The metrics for the runner.
        flavor: The flavor of the runner.
        job_metrics: The metrics about the job run by the runner.

    Returns:
        A set of issued events.
    """
    runner_start_event = metrics.RunnerStart(
        timestamp=runner_metrics.pre_job.timestamp,
        flavor=flavor,
        workflow=runner_metrics.pre_job.workflow,
        repo=runner_metrics.pre_job.repository,
        github_event=runner_metrics.pre_job.event,
        idle=runner_metrics.pre_job.timestamp - runner_metrics.installed_timestamp,
        queue_duration=job_metrics.queue_duration if job_metrics else None,
    )
    try:
        metrics.issue_event(runner_start_event)
    except IssueMetricEventError:
        logger.exception(
            "Not able to issue RunnerStart metric for runner %s. "
            "Will not issue RunnerStop metric.",
            runner_metrics.runner_name,
        )
        # Return to not issuing RunnerStop metrics if RunnerStart metric could not be issued.
        return set()

    issued_events = {metrics.RunnerStart}

    if runner_metrics.post_job:
        runner_stop_event = metrics.RunnerStop(
            timestamp=runner_metrics.post_job.timestamp,
            flavor=flavor,
            workflow=runner_metrics.pre_job.workflow,
            repo=runner_metrics.pre_job.repository,
            github_event=runner_metrics.pre_job.event,
            status=runner_metrics.post_job.status,
            status_info=runner_metrics.post_job.status_info,
            job_duration=runner_metrics.post_job.timestamp - runner_metrics.pre_job.timestamp,
            job_conclusion=job_metrics.conclusion if job_metrics else None,
        )
        try:
            metrics.issue_event(runner_stop_event)
        except IssueMetricEventError:
            logger.exception(
                "Not able to issue RunnerStop metric for runner %s.", runner_metrics.runner_name
            )
            return issued_events

        issued_events.add(metrics.RunnerStop)

    return issued_events
