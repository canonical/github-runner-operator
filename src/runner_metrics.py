#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and function to extract the metrics from a shared filesystem."""

import json
import logging
from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, Type
from urllib.error import HTTPError

from ghapi.core import GhApi
from ghapi.page import paged
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


IssuedMetricEventsStats = dict[Type[metrics.Event], int]


class GithubJobStats(BaseModel):
    """Stats for a job on GitHub.

    Args:
        created_at: The time the job was created.
        started_at: The time the job was started.
    """

    created_at: datetime
    started_at: datetime


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


class PostJobStatus(str, Enum):
    """The status of the post-job phase of a runner."""

    NORMAL = "normal"
    REPO_POLICY_CHECK_FAILURE = "repo-policy-check-failure"


class PostJobMetrics(BaseModel):
    """Metrics for the post-job phase of a runner.

    Args:
        timestamp: The UNIX time stamp of the time at which the event was originally issued.
        status: The status of the job.
    """

    timestamp: NonNegativeFloat
    status: PostJobStatus


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
        logger.debug("Runner %s installed at %s", fs.runner_name, installed_timestamp)
    except FileNotFoundError:
        logger.exception("installed_timestamp not found for runner %s", fs.runner_name)
        return None

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


def _issue_runner_metrics(
    runner_metrics: RunnerMetrics, flavor: str, queue_duration: Optional[float]
) -> IssuedMetricEventsStats:
    """Issue metrics.

    Converts the metrics into respective metric events and issues them.

    Args:
        runner_metrics: The metrics to be issued.
        flavor: The flavor of the runners.
        queue_duration: The time in seconds the job took before the runner picked it up.

    Returns:
        A dictionary containing the number of issued events per event type.
    """
    runner_start_event = metrics.RunnerStart(
        timestamp=runner_metrics.pre_job.timestamp,
        flavor=flavor,
        workflow=runner_metrics.pre_job.workflow,
        repo=runner_metrics.pre_job.repository,
        github_event=runner_metrics.pre_job.event,
        idle=runner_metrics.pre_job.timestamp - runner_metrics.installed_timestamp,
        queue_duration=queue_duration,
    )
    metrics.issue_event(runner_start_event)
    stats = {metrics.RunnerStart: 1}

    if runner_metrics.post_job:
        runner_stop_event = metrics.RunnerStop(
            timestamp=runner_metrics.post_job.timestamp,
            flavor=flavor,
            workflow=runner_metrics.pre_job.workflow,
            repo=runner_metrics.pre_job.repository,
            github_event=runner_metrics.pre_job.event,
            status=runner_metrics.post_job.status,
            job_duration=runner_metrics.post_job.timestamp - runner_metrics.pre_job.timestamp,
        )
        metrics.issue_event(runner_stop_event)
        stats[metrics.RunnerStop] = 1

    return stats


def _find_job_on_github(
    ghapi: GhApi, owner: str, repo: str, workflow_run_id: str, runner_name: str
) -> GithubJobStats:
    """Find a job for a workflow run on GitHub and return the job stats.

    Args:
        ghapi: The GitHub API client.
        owner: The owner of the repository.
        repo: The repository name.
        workflow_run_id: The workflow run id.
        runner_name: The name of the runner.
    Returns:
        The job stats.
    Raises:
        JobNotFoundOnGithubError: Raised if the job data could not be retrieved.
    """
    paged_kwargs = {"owner": owner, "repo": repo, "run_id": workflow_run_id}
    try:
        for wf_run_page in paged(ghapi.actions.list_jobs_for_workflow_run, **paged_kwargs):
            jobs = wf_run_page["jobs"]
            # ghapi performs endless pagination,
            # so we have to break out of the loop if there are no more jobs
            if not jobs:
                break
            for job in jobs:
                if job["runner_name"] == runner_name:
                    # datetime strings should be in ISO 8601 format,
                    # but they can also use Z instead of
                    # +00:00, which is not supported by datetime.fromisoformat
                    created_at = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                    started_at = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                    return GithubJobStats(created_at=created_at, started_at=started_at)

    except HTTPError as exc:
        raise errors.JobNotFoundOnGithubError(
            f"Could not find job for runner {runner_name}. "
            f"Could not list jobs for workflow run {workflow_run_id}"
        ) from exc

    raise errors.JobNotFoundOnGithubError(f"Could not find job for runner {runner_name}.")


def _calculate_job_queue_duration(
    ghapi: GhApi, pre_job_metrics: PreJobMetrics, runner_name: str
) -> float:
    """Calculate the job queue duration.

    The Github API is accessed to retrieve the job data for the runner, which includes
    the time the job was created and the time the job was started.

    Args:
        ghapi: The GitHub API client.
        pre_job_metrics: The pre-job metrics.
        runner_name: The name of the runner.

    Returns:
        The time in seconds the job took before the runner picked it up.
    """
    owner, repo = pre_job_metrics.repository.split("/", maxsplit=1)

    job = _find_job_on_github(
        ghapi=ghapi,
        owner=owner,
        repo=repo,
        workflow_run_id=pre_job_metrics.workflow_run_id,
        runner_name=runner_name,
    )
    duration = (job.started_at - job.created_at).total_seconds()

    return duration


def _clean_up_shared_fs(fs: shared_fs.SharedFilesystem) -> None:
    """Clean up the shared filesystem.

    Remove all metric files and afterwards the shared filesystem.
    Args:
        fs: The shared filesystem for a specific runner.
    """
    try:
        fs.path.joinpath(RUNNER_INSTALLED_TS_FILE_NAME).unlink(missing_ok=True)
        fs.path.joinpath(PRE_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
        fs.path.joinpath(POST_JOB_METRICS_FILE_NAME).unlink(missing_ok=True)
    except OSError:
        logger.exception(
            "Could not remove metric files for runner %s, "
            "this may lead to duplicate metrics issued",
            fs.runner_name,
        )

    try:
        shared_fs.delete(fs.runner_name)
    except errors.DeleteSharedFilesystemError:
        logger.exception("Could not delete shared filesystem for runner %s.", fs.runner_name)


def _extract_fs(
    runner_fs: shared_fs.SharedFilesystem, flavor: str, gh_api: GhApi
) -> IssuedMetricEventsStats:
    """Extract and issue metrics from a shared filesystem.

    Args:
        runner_fs: The shared filesystem for a specific runner.
        flavor: The flavor of the runner.
        gh_api: The GitHub API client.

    Returns:
        A dictionary containing the number of issued events per event type.
    """
    runner_name = runner_fs.runner_name
    try:
        logger.debug("Extracting metrics from shared filesystem for runner %s", runner_name)
        metrics_from_fs = _extract_metrics_from_fs(runner_fs)
    except CorruptMetricDataError:
        logger.exception("Corrupt metric data found for runner %s", runner_name)
        shared_fs.move_to_quarantine(runner_name)
        return {}

    stats = {}
    if metrics_from_fs:
        try:
            jq_duration = _calculate_job_queue_duration(
                ghapi=gh_api, pre_job_metrics=metrics_from_fs.pre_job, runner_name=runner_name
            )
        except errors.JobNotFoundOnGithubError:
            logger.exception("Not able to calculate queue duration for runner %s", runner_name)
            jq_duration = None
        try:
            stats = _issue_runner_metrics(
                runner_metrics=metrics_from_fs, flavor=flavor, queue_duration=jq_duration
            )
        except errors.IssueMetricEventError:
            logger.exception("Not able to issue metrics for runner %s", runner_name)
    else:
        logger.warning("Not able to issue metrics for runner %s", runner_name)

    logger.debug("Cleaning up shared filesystem for runner %s", runner_name)
    _clean_up_shared_fs(runner_fs)
    return stats


def extract(flavor: str, ignore_runners: set[str], gh_api: GhApi) -> IssuedMetricEventsStats:
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
        gh_api: The GitHub API client.

    Returns:
        A dictionary containing the number of issued events per event type.
    """
    total_stats: IssuedMetricEventsStats = {}
    for fs in shared_fs.list_all():
        if fs.runner_name not in ignore_runners:
            stats = _extract_fs(runner_fs=fs, flavor=flavor, gh_api=gh_api)
            for event_type, count in stats.items():
                total_stats[event_type] = total_stats.get(event_type, 0) + count
    return total_stats
