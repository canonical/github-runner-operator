#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to calculate metrics from data retrieved from GitHub."""

from charm_state import GithubRepo
from errors import GithubMetricsError, JobNotFoundError
from github_client import GithubClient
from metrics.runner import PreJobMetrics
from metrics.type import GithubJobMetrics


def job(
    github_client: GithubClient, pre_job_metrics: PreJobMetrics, runner_name: str
) -> GithubJobMetrics:
    """Calculate the job metrics for a runner.

    The Github API is accessed to retrieve the job data for the runner.

    Args:
        github_client: The GitHub API client.
        pre_job_metrics: The pre-job metrics.
        runner_name: The name of the runner.

    Raises:
        GithubMetricsError: If the job for given workflow run is not found.

    Returns:
        The job metrics.
    """
    owner, repo = pre_job_metrics.repository.split("/", maxsplit=1)

    try:
        job_info = github_client.get_job_info(
            path=GithubRepo(owner=owner, repo=repo),
            workflow_run_id=pre_job_metrics.workflow_run_id,
            runner_name=runner_name,
        )
    except JobNotFoundError as exc:
        raise GithubMetricsError from exc
    queue_duration = (job_info.started_at - job_info.created_at).total_seconds()

    return GithubJobMetrics(queue_duration=queue_duration, conclusion=job_info.conclusion)
