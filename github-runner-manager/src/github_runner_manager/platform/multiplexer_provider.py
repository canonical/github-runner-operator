# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Multiplexer platform provider to use several providers simultaneously."""

from collections import defaultdict
from typing import Iterable

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.manager.models import InstanceID, RunnerContext, RunnerMetadata
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.platform.jobmanager_provider import JobManagerPlatform
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerHealth,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import SelfHostedRunner


class MultiplexerPlatform(PlatformProvider):
    """Manage self-hosted runner on the Multiplexer.

    The Multiplexer platform provider serves as an interface to use several
    platform providers simultaneously. In that way, one runner manager can use for example
    GitHub and JobManager providers together. The multiplexer will route the requests
    to the adequate provider..
    """

    def __init__(self, providers: dict[str, PlatformProvider]):
        """Construct the object.

        Args:
            providers: dict of providers to use for multiplexing.
        """
        self._providers = providers

    @classmethod
    def build(
        cls, prefix: str, github_configuration: GitHubConfiguration
    ) -> "MultiplexerPlatform":
        """Build a new MultiplexerPlatform.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration

        Returns:
            A new MultiplexerPlatform.
        """
        github_platform = GitHubRunnerPlatform.build(prefix, github_configuration)
        jobmanager_platform = JobManagerPlatform.build()
        return cls({"github": github_platform, "jobmanager": jobmanager_platform})

    def get_runner_health(
        self,
        metadata: RunnerMetadata,
        instance_id: InstanceID,
    ) -> PlatformRunnerHealth:
        """Get health information on self-hosted runner.

        Args:
            metadata: Metadata for the runner.
            instance_id: Instance ID of the runner.

        Returns:
            Platform Runner Health information.
        """
        return self._get_provider(metadata).get_runner_health(metadata, instance_id)

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Get the list of runners from all platforms.
        """
        # FIXME. This method should not exist as the jobmanager does not offer a API to
        # get all runners (at least not for the github-runner). We should delete this method
        # and instead get all runners from the cloud manager.
        # A method to delete all runners in the platform that are not in the cloud manager
        # may also be needed, for example github may need to have this, so there are no runners
        # in offline/idle state without a cloud instance.
        runners = ()
        for platform in self._providers.values():
            runners += platform.get_runners(states)
        return runners

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners.

        Args:
            runners: list of runners to delete.
        """
        # FIXME. This method should disappear. Instead a delete_runner method
        # should be created that can be checked. This is specially important for
        # github, as the API can return 422, in case the runner is in (online, busy),
        # in which case the caller can decide if the cloud runner should be deleted or not
        platform_runners: dict[str, PlatformProvider] = defaultdict(list)
        for runner in runners:
            platform_runners[runner.metadata.platform_name].append(runner)

        for platform_name, platform_runners in platform_runners.items():
            self._providers[platform_name].delete_runners(platform_runners)

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

    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.

        Returns:
            The removal token..
        """
        # FIXME. This method should not exist. There should be just a method to delete a runner,
        # For now, the github implementation is just used to not break the reconcile loop.
        return self._providers["github"].get_removal_token()

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
