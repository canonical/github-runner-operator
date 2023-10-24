#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from a shared filesystem."""

import json
import logging
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, NonNegativeFloat, ValidationError

import errors
import metrics
import shared_fs
from errors import CorruptMetricDataError

logger = logging.getLogger(__name__)

FILE_SIZE_BYTES_LIMIT = 1024
PRE_JOB_METRICS_FILE_NAME = "pre-job-metrics.json"
POST_JOB_METRICS_FILE_NAME = "post-job-metrics.json"
RUNNER_INSTALLED_TS_FILE_NAME = "runner-installed.timestamp"


class PreJobMetrics(BaseModel):
    """Metrics for the pre-job phase of a runner.

    Args:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        workflow: The workflow name.
        workflow_run_id: The workflow run id.
        repository: The repository name.
        event: The github event.
    """

    timestamp: NonNegativeFloat
    workflow: str
    workflow_run_id: str
    repository: str
    event: str


class PostJobMetrics(BaseModel):
    """Metrics for the post-job phase of a runner.

    Args:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        status: The status of the job.
    """

    timestamp: NonNegativeFloat
    status: str


class RunnerMetrics(BaseModel):
    """Metrics for a runner.

    Args:
        installed_timestamp: The UNIX time stamp of the time at which the runner was installed.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
    """

    installed_timestamp: NonNegativeFloat
    pre_job: PreJobMetrics
    post_job: Optional[PostJobMetrics]


def _inspect_file_sizes(fs: shared_fs.SharedFilesystem) -> tuple[Path, ...]:
    """Inspect the file sizes of the shared filesystem.

    Args:
        fs: The shared filesystem for a specific runner.

    Returns:
        A tuple of files whose size is larger than the limit.
    """
    files: list[Path] = [
        fs.path.joinpath(PRE_JOB_METRICS_FILE_NAME),
        fs.path.joinpath(POST_JOB_METRICS_FILE_NAME),
        fs.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME),
    ]

    return tuple(
        filter(lambda file: file.exists() and file.stat().st_size > FILE_SIZE_BYTES_LIMIT, files)
    )


def _extract_metrics_from_fs(fs: shared_fs.SharedFilesystem) -> Optional[RunnerMetrics]:
    """Extract metrics from a shared filesystem.

    Args:
        fs: The shared filesystem for a specific runner.

    Returns:
        The extracted metrics if at least the pre-job metrics are present.

    Raises:
        CorruptMetricDataError: Raised if one of the files is not valid or too large.
    """
    if too_large_files := _inspect_file_sizes(fs):
        raise CorruptMetricDataError(
            f"File size of {too_large_files} is too large. "
            f"The limit is {FILE_SIZE_BYTES_LIMIT} bytes."
        )

    try:
        installed_timestamp = fs.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).read_text()
    except FileNotFoundError:
        logger.exception("installed_timestamp not found for runner %s", fs.runner_name)
        return None

    logger.debug("Runner %s installed at %s", fs.runner_name, installed_timestamp)
    try:
        pre_job_metrics = json.loads(fs.path.joinpath(PRE_JOB_METRICS_FILE_NAME).read_text())
        logger.debug("Pre-job metrics for runner %s: %s", fs.runner_name, pre_job_metrics)
    except FileNotFoundError:
        logger.warning("%s not found for runner %s.", PRE_JOB_METRICS_FILE_NAME, fs.runner_name)
        return None
    except JSONDecodeError as exc:
        raise CorruptMetricDataError(str(exc)) from exc

    try:
        post_job_metrics = json.loads(fs.path.joinpath(POST_JOB_METRICS_FILE_NAME).read_text())
        logger.debug("Post-job metrics for runner %s: %s", fs.runner_name, post_job_metrics)
    except FileNotFoundError:
        logger.warning("%s not found for runner %s", POST_JOB_METRICS_FILE_NAME, fs.runner_name)
        post_job_metrics = None
    except JSONDecodeError as exc:
        raise CorruptMetricDataError(str(exc)) from exc

    if not isinstance(pre_job_metrics, dict):
        raise CorruptMetricDataError(
            f"Pre-job metrics for runner {fs.runner_name} is not a JSON object."
        )

    if not isinstance(post_job_metrics, dict) and post_job_metrics is not None:
        raise CorruptMetricDataError(
            f"Post-job metrics for runner {fs.runner_name} is not a JSON object."
        )

    try:
        return RunnerMetrics(
            installed_timestamp=installed_timestamp,
            pre_job=PreJobMetrics(**pre_job_metrics),
            post_job=PostJobMetrics(**post_job_metrics) if post_job_metrics else None,
        )
    except ValidationError as exc:
        raise CorruptMetricDataError(str(exc)) from exc


def _issue_runner_metrics(runner_metrics: RunnerMetrics, flavor: str) -> None:
    """Issue metrics.

    Converts the metrics into respective metric events and issues them.

    Args:
        runner_metrics: The metrics to be issued.
        flavor: The flavor of the runners.
    """
    event = metrics.RunnerStart(
        timestamp=runner_metrics.pre_job.timestamp,
        flavor=flavor,
        workflow=runner_metrics.pre_job.workflow,
        repo=runner_metrics.pre_job.repository,
        github_event=runner_metrics.pre_job.event,
        idle=runner_metrics.pre_job.timestamp - runner_metrics.installed_timestamp,
    )
    metrics.issue_event(event)


def _clean_up_shared_fs(fs: shared_fs.SharedFilesystem) -> None:
    """Clean up the shared filesystem.

    Remove all metric files and afterwards the shared filesystem.
    Args:
        fs: The shared filesystem for a specific runner.
    """
    fs.path.joinpath(PRE_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
    fs.path.joinpath(POST_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
    fs.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).unlink(missing_ok=True)

    try:
        shared_fs.delete(fs.runner_name)
    except errors.DeleteSharedFilesystemError:
        logger.exception("Could not delete shared filesystem for runner %s.", fs.runner_name)


def extract(flavor: str, ignore_runners: set[str]) -> None:
    """Extract and issue metrics from runners.

    The metrics are extracted from the shared filesystem of given runners
    and respective metric events are issued.
    Orphan shared filesystems are cleaned up.

    If corrupt data is found, an error is raised immediately, as this may indicate that a malicious
    runner is trying to manipulate the shared file system.
    In order to avoid DoS attacks, the file size is also checked.

    Args:
        flavor: The flavor of the runners to extract metrics from.
        ignore_runners: The set of runners to ignore.

    Raises:
        CorruptMetricDataError: If one of the files inside the shared filesystem is not valid.
    """
    for fs in shared_fs.list_all():
        if fs.runner_name not in ignore_runners:
            metrics_from_fs = _extract_metrics_from_fs(fs)

            if metrics_from_fs:
                try:
                    _issue_runner_metrics(runner_metrics=metrics_from_fs, flavor=flavor)
                except errors.IssueMetricEventError:
                    logger.exception("Not able to issue metrics for runner %s", fs.runner_name)
            else:
                logger.warning("Not able to issue metrics for runner %s", fs.runner_name)

            logger.debug("Cleaning up shared filesystem for runner %s", fs.runner_name)
            _clean_up_shared_fs(fs)
