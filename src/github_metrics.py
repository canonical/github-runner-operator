# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to calculate metrics from data retrieved from GitHub."""
import errors
from github_client import GithubClient
from runner_metrics import PreJobMetrics
from runner_type import GithubRepo


def job_queue_duration(
    github_client: GithubClient, pre_job_metrics: PreJobMetrics, runner_name: str
) -> float:
    """Calculate the job queue duration.

    The Github API is accessed to retrieve the job data for the runner, which includes
    the time the job was created and the time the job was started.

    Args:
        github_client: The GitHub API client.
        pre_job_metrics: The pre-job metrics.
        runner_name: The name of the runner.

    Returns:
        The time in seconds the job took before the runner picked it up.
    """
    owner, repo = pre_job_metrics.repository.split("/", maxsplit=1)

    try:
        job = github_client.get_job_info(
            path=GithubRepo(owner=owner, repo=repo),
            workflow_run_id=pre_job_metrics.workflow_run_id,
            runner_name=runner_name,
        )
    except errors.JobNotFoundError as exc:
        raise errors.GithubMetricsError from exc
    duration = (job.started_at - job.created_at).total_seconds()

    return duration
