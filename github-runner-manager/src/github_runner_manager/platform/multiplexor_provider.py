# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Many not implemented methods equal to the jobmanager.
# pylint:disable=duplicate-code

"""Multiplexor platform provider."""

from collections import defaultdict
from typing import Iterable

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.platform.jobmanager_provider import JobManagerPlatform
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import SelfHostedRunner


class MultiplexorPlatform(PlatformProvider):
    """Manage self-hosted runner on the Multiplexor."""

    def __init__(self, providers: dict[str, PlatformProvider]):
        """Construct the object.

        Args:
            providers: TODO
        """
        self._providers = providers

    @classmethod
    def build(
        cls, prefix: str, github_configuration: GitHubConfiguration
    ) -> "MultiplexorPlatform":
        """Build a TODO.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration

        Returns:
            A new GitHubRunnerPlatform.
        """
        github_platform = GitHubRunnerPlatform.build(prefix, github_configuration)
        jobmanager_platform = JobManagerPlatform.build(prefix)
        return cls({"github": github_platform, "jobmanager": jobmanager_platform})

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            TODO
        """
        # TODO THIS IS PROBABLY WRONG. IF THE JOBMANAGER DOES NOT OFFER AN API TO
        # GET ALL RUNNERS, WE SHOULD DELETE THIS FUNCTION AND GET THEM FROM THE
        # CLOUD MANAGER. IN THAT CASE, A FUNCTION TO DELETE STRAY RUNNERS IN THE
        # PLATFORM PROVIDER SHOULD BE CREATED. THAT IS TO DELETE (OFFLINE, IDLE) IN GITHUB
        # SO THEY DO NOT ROAM FOR A FULL DAY IF THEY (DELETE THEM ONCE WHEY ARE OLDER
        # THAN 15/20 MIN, TO GIVE THE RUNNER ENOUGH TIME TO GET ONLINE)
        # todo why a tuple??
        runners = ()
        for platform in self._providers.values():
            runners += platform.get_runners(states)
        return runners

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners.

        Args:
            runners: list of runners to delete.
        """
        # TODO THIS FUNCTIONS IS WRONG. SelfHostedRunner should include a platform name
        platform_runners: dict[str, PlatformProvider] = defaultdict(list)
        for runner in runners:
            platform_runners[runner.metadata.platform_name].append(runner)

        for platform_name, platform_runners in platform_runners.items():
            # TODO HANDLE ERRORS BETTER.
            self._providers[platform_name].delete_runners(platform_runners)

    def get_runner_token(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get a one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: Metadata for the runner.
            labels: Labels for the runner.

        Returns:
            TODO
        """
        return self._get_provider(metadata).get_runner_token(metadata, instance_id, labels)

    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.

        Returns:
            TODO.
        """
        # TODO. THIS IS WRONG. THIS FUNCTION SHOULD DISAPPEAR AND BE RELATED TO A SPECIFIC RUNNER
        # LEFT HERE TO USE GITHUB TO NOT BREAK THE RECONCILE LOOP.
        return self._providers["github"].get_removal_token()

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
            metadata: Metadata for the runner.


        Returns:
            TODO.
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
            TODO.
        """
        return self._get_provider(metadata).get_job_info(
            metadata, repository, workflow_run_id, runner
        )

    def _get_provider(self, metadata: RunnerMetadata) -> PlatformProvider:
        """TODO."""
        # TODO, raise if wrong and those things
        return self._providers[metadata.platform_name]
