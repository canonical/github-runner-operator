# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""JobManager platform provider."""

from typing import Iterable

from pydantic import HttpUrl

from github_runner_manager.manager.models import InstanceID
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import SelfHostedRunner


class JobManagerPlatform(PlatformProvider):
    """This class defines the API and the base class for a platform."""

    def __init__(self, prefix: str):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.

        Raises:
            NotImplementedError: Work in progress
        """
        self._prefix = prefix
        raise NotImplementedError

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners in GitHub.

        Args:
            runners: list of runners to delete.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def get_runner_token(
        self, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def check_job_been_picked_up(self, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def get_job_info(self, repository: str, workflow_run_id: str, runner: InstanceID) -> JobInfo:
        """Check if the job has already been picked up.

        Args:
            repository: TODO
            workflow_run_id: TODO
            runner: TODO

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError
