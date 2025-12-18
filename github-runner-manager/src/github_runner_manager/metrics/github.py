#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions to calculate metrics from data retrieved from GitHub."""
import logging

from prometheus_client import Counter

from github_runner_manager.errors import GithubMetricsError
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.metrics.runner import PreJobMetrics
from github_runner_manager.metrics.type import GithubJobMetrics
from github_runner_manager.platform.platform_provider import (
    JobNotFoundError,
    PlatformApiError,
    PlatformProvider,
)

logger = logging.getLogger(__name__)

# Status code used for non-HTTP errors in metrics
STATUS_CODE_NOT_AVAILABLE = "n/a"

# Prometheus metrics for GitHub API calls
GITHUB_API_REQUESTS_TOTAL = Counter(
    name="github_api_requests_total",
    documentation="Total number of GitHub API requests by endpoint",
    labelnames=["endpoint"],
)
GITHUB_API_ERRORS_TOTAL = Counter(
    name="github_api_errors_total",
    documentation="Total number of GitHub API errors by endpoint and status code",
    labelnames=["endpoint", "status_code"],
)


def job(
    platform_provider: PlatformProvider,
    pre_job_metrics: PreJobMetrics,
    runner: InstanceID,
    metadata: RunnerMetadata,
) -> GithubJobMetrics:
    """Calculate the job metrics for a runner.

    The Github API is accessed to retrieve the job data for the runner.

    Args:
        platform_provider: The platform provider.
        pre_job_metrics: The pre-job metrics.
        runner: The runner instance id.
        metadata: Metadata for the runner.

    Raises:
        GithubMetricsError: If the job for given workflow run is not found.

    Returns:
        The job metrics.
    """
    try:
        job_info = platform_provider.get_job_info(
            metadata=metadata,
            repository=pre_job_metrics.repository,
            workflow_run_id=pre_job_metrics.workflow_run_id,
            runner=runner,
        )
    except (JobNotFoundError, PlatformApiError) as exc:
        raise GithubMetricsError from exc

    queue_duration = (job_info.started_at - job_info.created_at).total_seconds()

    return GithubJobMetrics(queue_duration=queue_duration, conclusion=job_info.conclusion)
