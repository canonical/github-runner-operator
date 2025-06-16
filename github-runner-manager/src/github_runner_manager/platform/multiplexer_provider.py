# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Multiplexer platform provider to use several providers simultaneously."""

import logging
from collections import defaultdict
from enum import Enum

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.platform.jobmanager_provider import JobManagerPlatform
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformError,
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import SelfHostedRunner

_GITHUB_PLATFORM_KEY = "github"
_JOBMANAGER_PLATFORM_KEY = "jobmanager"

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    """Enum for supported platforms.

    Attributes:
        GITHUB: GitHub platform.
        JOBMANAGER: JobManager platform.
    """

    GITHUB = _GITHUB_PLATFORM_KEY
    JOBMANAGER = _JOBMANAGER_PLATFORM_KEY


class MultiplexerPlatform(PlatformProvider):
    """Manage self-hosted runner on the Multiplexer.

    The Multiplexer platform provider serves as an interface to use several
    platform providers simultaneously. In that way, one runner manager can use for example
    GitHub and JobManager providers together. The multiplexer will route the requests
    to the adequate provider.
    """

    def __init__(self, providers: dict[str, PlatformProvider]):
        """Construct the object.

        Args:
            providers: dict of providers to use for multiplexing.
        """
        self._providers = providers

    @classmethod
    def build(
        cls,
        prefix: str,
        github_configuration: GitHubConfiguration | None,
        jobmanager_configuration: JobManagerConfiguration | None = None,
    ) -> "MultiplexerPlatform":
        """Build a new MultiplexerPlatform.

        Multiple platform providers can be used simultaneously, such as GitHub and JobManager.
        At least one is required to create the MultiplexerPlatform.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration
            jobmanager_configuration: JobManager configuration

        Raises:
            PlatformError: If no configuration is provided for any platform.

        Returns:
            A new MultiplexerPlatform.
        """
        providers: dict[str, PlatformProvider] = {}

        if jobmanager_configuration is None:
            logger.debug("JobManager configuration not provided, skipping JobManager provider.")
        else:
            jobmanager_platform = JobManagerPlatform.build(jobmanager_configuration)
            providers.update({_JOBMANAGER_PLATFORM_KEY: jobmanager_platform})
        if github_configuration is None:
            logger.debug("GitHub configuration not provided, skipping GitHub provider.")
        else:
            github_platform = GitHubRunnerPlatform.build(prefix, github_configuration)
            providers.update({_GITHUB_PLATFORM_KEY: github_platform})

        if not providers:
            raise PlatformError("Either GitHub or JobManager configuration must be provided.")
        return cls(providers)

    def get_runner_health(
        self,
        runner_identity: RunnerIdentity,
    ) -> PlatformRunnerHealth:
        """Get health information on self-hosted runner.

        Args:
            runner_identity: Identity of the runner.

        Returns:
            Platform Runner Health information.
        """
        return self._get_provider(runner_identity.metadata).get_runner_health(runner_identity)

    def get_runners_health(self, requested_runners: list[RunnerIdentity]) -> RunnersHealthResponse:
        """Get information from the requested runners health.

        Args:
            requested_runners: List of runners to get health information for.

        Returns:
            Health information for the runners.
        """
        response = RunnersHealthResponse()
        identities_by_provider: dict[str, RunnerIdentity] = defaultdict(list)
        for identity in requested_runners:
            identities_by_provider[identity.metadata.platform_name].append(identity)
        # Call all of them, whether there is data or not
        for platform_name in self._providers:
            platform_identities = identities_by_provider.get(platform_name, [])
            provider_health_response = self._providers[platform_name].get_runners_health(
                platform_identities
            )
            response.append(provider_health_response)
        return response

    def delete_runner(self, runner_identity: RunnerIdentity) -> None:
        """Delete a  runner.

        Args:
            runner_identity: Runner to delete.
        """
        self._get_provider(runner_identity.metadata).delete_runner(runner_identity)

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get a one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: Metadata for the runner.
            labels: Labels for the runner.

        Returns:
            The runner token and the runner.
        """
        return self._get_provider(metadata).get_runner_context(metadata, instance_id, labels)

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
            metadata: Metadata for the runner.

        Returns:
            True if the job has been picked up, False otherwise.
        """
        return self._get_provider(metadata).check_job_been_picked_up(metadata, job_url)

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get the Job info from the provider.

        Args:
            metadata: Metadata for the runner.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.

        Returns:
            Information about the Job.
        """
        return self._get_provider(metadata).get_job_info(
            metadata, repository, workflow_run_id, runner
        )

    def _get_provider(self, metadata: RunnerMetadata) -> PlatformProvider:
        """Get the provider based on the RunnerMetadata."""
        return self._providers[metadata.platform_name]
