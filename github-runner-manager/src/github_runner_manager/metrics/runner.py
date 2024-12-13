#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from storage and issue runner metrics events."""

import json
import logging
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Iterator, Optional, Type

from pydantic import BaseModel, Field, NonNegativeFloat, ValidationError

from github_runner_manager.errors import (
    CorruptMetricDataError,
    DeleteMetricsStorageError,
    IssueMetricEventError,
    RunnerMetricsError,
)
from github_runner_manager.metrics import events as metric_events
from github_runner_manager.metrics.storage import MetricsStorage
from github_runner_manager.metrics.storage import StorageManagerProtocol as MetricsStorageManager
from github_runner_manager.metrics.type import GithubJobMetrics

logger = logging.getLogger(__name__)

FILE_SIZE_BYTES_LIMIT = 1024
PRE_JOB_METRICS_FILE_NAME = "pre-job-metrics.json"
POST_JOB_METRICS_FILE_NAME = "post-job-metrics.json"
RUNNER_INSTALLATION_START_TS_FILE_NAME = "runner-installation-start.timestamp"
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
        installation_start_timestamp: The UNIX time stamp of the time at which the runner
            installation started.
        installed_timestamp: The UNIX time stamp of the time at which the runner was installed.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
        runner_name: The name of the runner.
    """

    installation_start_timestamp: NonNegativeFloat | None
    installed_timestamp: NonNegativeFloat
    pre_job: PreJobMetrics | None
    post_job: PostJobMetrics | None
    runner_name: str


def extract(
    metrics_storage_manager: MetricsStorageManager, runners: set[str], include: bool = False
) -> Iterator[RunnerMetrics]:
    """Extract metrics from runners.

    The metrics are extracted from the metrics storage of the runners.
    Orphan storages are cleaned up.

    If corrupt data is found, the metrics are not processed further and the storage is moved
    to a special quarantine directory, as this may indicate that a malicious
    runner is trying to manipulate the files on the storage.

    In order to avoid DoS attacks, the file size is also checked.

    Args:
        metrics_storage_manager: The metrics storage manager.
        runners: The runners to include or exclude.
        include: If true the provided runners are included for metric extraction, else the provided
            runners are excluded.

    Yields:
        Extracted runner metrics of a particular runner.
    """
    for ms in metrics_storage_manager.list_all():
        if (include and ms.runner_name in runners) or (
            not include and ms.runner_name not in runners
        ):
            runner_metrics = _extract_storage(
                metrics_storage_manager=metrics_storage_manager, metrics_storage=ms
            )
            if not runner_metrics:
                logger.warning("Not able to issue metrics for runner %s", ms.runner_name)
            else:
                yield runner_metrics


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
                runner_metrics.runner_name,
            )
    except (ValidationError, IssueMetricEventError):
        if runner_metrics.installation_start_timestamp and not issued_events:
            logger.exception(
                "Not able to issue RunnerInstalled metric for runner %s with"
                " installation_start_timestamp %s."
                "Will not issue RunnerStart and RunnerStop metric.",
                runner_metrics.runner_name,
                runner_metrics.installation_start_timestamp,
            )
        elif metric_events.RunnerStart not in issued_events:
            logger.exception(
                "Not able to issue RunnerStart metric for "
                "runner %s with pre-job metrics %s and job_metrics %s."
                "Will not issue RunnerStop metric.",
                runner_metrics.runner_name,
                runner_metrics.pre_job,
                job_metrics,
            )
        else:
            logger.exception(
                "Not able to issue RunnerStop metric for "
                "runner %s with pre-job metrics %s, post-job metrics %s and job_metrics %s.",
                runner_metrics.runner_name,
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
    logger.debug("Issuing RunnerInstalled metric for runner %s", runner_metrics.runner_name)
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

    logger.debug("Issuing RunnerStart metric for runner %s", runner_metrics.runner_name)
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

    logger.debug("Issuing RunnerStop metric for runner %s", runner_metrics.runner_name)
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
            runner_metrics.runner_name,
        )
    idle_duration = max(pre_job_metrics.timestamp - runner_metrics.installed_timestamp, 0)

    # GitHub API returns started_at < created_at in some rare cases.
    if job_metrics and job_metrics.queue_duration < 0:
        logger.warning(
            "Queue duration for runner %s is negative: %f. Setting it to zero.",
            runner_metrics.runner_name,
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
            runner_metrics.runner_name,
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


def _extract_storage(
    metrics_storage_manager: MetricsStorageManager,
    metrics_storage: MetricsStorage,
) -> Optional[RunnerMetrics]:
    """Extract metrics from a metrics storage.

    Args:
        metrics_storage_manager: The metrics storage manager.
        metrics_storage: The metrics storage for a specific runner.

    Returns:
        The extracted metrics if at least the runner installed timestamp is present.
    """
    runner_name = metrics_storage.runner_name
    try:
        logger.debug("Extracting metrics from metrics storage for runner %s", runner_name)
        metrics_from_fs = _extract_metrics_from_storage(metrics_storage)
    except CorruptMetricDataError:
        logger.exception("Corrupt metric data found for runner %s", runner_name)
        metrics_storage_manager.move_to_quarantine(runner_name)
        return None

    logger.debug("Cleaning metrics storage for runner %s", runner_name)
    _clean_up_storage(
        metrics_storage_manager=metrics_storage_manager, metrics_storage=metrics_storage
    )
    return metrics_from_fs


def _extract_metrics_from_storage(metrics_storage: MetricsStorage) -> Optional[RunnerMetrics]:
    """Extract metrics from metrics storage for a runner.

    Args:
        metrics_storage: The metrics storage for a specific runner.

    Returns:
        The extracted metrics if at least the installed timestamp is present.

    Raises:
        CorruptMetricDataError: Raised if one of the files is not valid or too large.
    """
    if too_large_files := _inspect_file_sizes(metrics_storage):
        raise CorruptMetricDataError(
            f"File size of {too_large_files} is too large. "
            f"The limit is {FILE_SIZE_BYTES_LIMIT} bytes."
        )

    runner_name = metrics_storage.runner_name

    installation_start_timestamp = _extract_file_from_storage(
        metrics_storage=metrics_storage, filename=RUNNER_INSTALLATION_START_TS_FILE_NAME
    )
    logger.debug("Runner %s installation started at %s", runner_name, installation_start_timestamp)

    installed_timestamp = _extract_file_from_storage(
        metrics_storage=metrics_storage, filename=RUNNER_INSTALLED_TS_FILE_NAME
    )
    if not installed_timestamp:
        logger.error(
            "installed timestamp not found for runner %s, will not extract any metrics.",
            runner_name,
        )
        return None
    logger.debug("Runner %s installed at %s", runner_name, installed_timestamp)

    pre_job_metrics = _extract_json_file_from_storage(
        metrics_storage=metrics_storage, filename=PRE_JOB_METRICS_FILE_NAME
    )
    if pre_job_metrics:

        logger.debug("Pre-job metrics for runner %s: %s", runner_name, pre_job_metrics)

        post_job_metrics = _extract_json_file_from_storage(
            metrics_storage=metrics_storage, filename=POST_JOB_METRICS_FILE_NAME
        )
        logger.debug("Post-job metrics for runner %s: %s", runner_name, post_job_metrics)
    else:
        logger.error(
            "Pre-job metrics for runner %s not found, stop extracting post-jobs metrics.",
            runner_name,
        )
        post_job_metrics = None

    try:
        return RunnerMetrics(
            installation_start_timestamp=(
                float(installation_start_timestamp) if installation_start_timestamp else None
            ),
            installed_timestamp=float(installed_timestamp),
            pre_job=PreJobMetrics(**pre_job_metrics) if pre_job_metrics else None,
            post_job=PostJobMetrics(**post_job_metrics) if post_job_metrics else None,
            runner_name=runner_name,
        )
    except ValueError as exc:
        raise CorruptMetricDataError(str(exc)) from exc


def _inspect_file_sizes(metrics_storage: MetricsStorage) -> tuple[Path, ...]:
    """Inspect the file sizes of the metrics storage.

    Args:
        metrics_storage: The metrics storage for a specific runner.

    Returns:
        A tuple of files whose size is larger than the limit.
    """
    files: list[Path] = [
        metrics_storage.path.joinpath(PRE_JOB_METRICS_FILE_NAME),
        metrics_storage.path.joinpath(POST_JOB_METRICS_FILE_NAME),
        metrics_storage.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME),
        metrics_storage.path.joinpath(RUNNER_INSTALLATION_START_TS_FILE_NAME),
    ]

    return tuple(
        filter(lambda file: file.exists() and file.stat().st_size > FILE_SIZE_BYTES_LIMIT, files)
    )


def _extract_json_file_from_storage(metrics_storage: MetricsStorage, filename: str) -> dict | None:
    """Extract a particular metric file from metrics storage.

    Args:
        metrics_storage: The metrics storage for a specific runner.
        filename: The metrics filename.

    Raises:
        CorruptMetricDataError: If any errors have been found within the metric.

    Returns:
        Metrics for the given runner if present.
    """
    job_metrics_raw = _extract_file_from_storage(
        metrics_storage=metrics_storage, filename=filename
    )
    if not job_metrics_raw:
        return None

    try:
        job_metrics = json.loads(job_metrics_raw)
    except JSONDecodeError as exc:
        raise CorruptMetricDataError(str(exc)) from exc
    if not isinstance(job_metrics, dict):
        raise CorruptMetricDataError(
            f"{filename} metrics for runner {metrics_storage.runner_name} is not a JSON object."
        )
    return job_metrics


def _extract_file_from_storage(metrics_storage: MetricsStorage, filename: str) -> str | None:
    """Extract a particular file from metrics storage.

    Args:
        metrics_storage: The metrics storage for a specific runner.
        filename: The metrics filename.

    Returns:
        Metrics for the given runner if present.
    """
    try:
        file_content = metrics_storage.path.joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.exception("%s not found for runner %s", filename, metrics_storage.runner_name)
        file_content = None
    return file_content


def _clean_up_storage(
    metrics_storage_manager: MetricsStorageManager, metrics_storage: MetricsStorage
) -> None:
    """Clean up the metrics storage.

    Remove all metric files and afterwards the storage.

    Args:
        metrics_storage_manager: The metrics storage manager.
        metrics_storage: The metrics storage for a specific runner.
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
    except DeleteMetricsStorageError:
        logger.exception(
            "Could not delete metrics storage for runner %s.", metrics_storage.runner_name
        )
