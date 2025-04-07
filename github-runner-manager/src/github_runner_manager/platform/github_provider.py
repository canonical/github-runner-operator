# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

import logging
from enum import Enum
from typing import Iterable

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubConfiguration, GitHubRepo
from github_runner_manager.github_client import GithubClient
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.platform.platform_provider import PlatformProvider, PlatformRunnerState
from github_runner_manager.types_.github import SelfHostedRunner

logger = logging.getLogger(__name__)


class GitHubRunnerPlatform(PlatformProvider):
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, github_configuration: GitHubConfiguration):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration information.
        """
        self._prefix = prefix
        self._path = github_configuration.path
        self._client = GithubClient(github_configuration.token)

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Information on the runners.
        """
        runner_list = self._client.get_runner_github_info(self._path, self._prefix)

        if states is None:
            return tuple(runner_list)

        state_set = set(states)
        return tuple(
            runner
            for runner in runner_list
            if GitHubRunnerPlatform._is_runner_in_state(runner, state_set)
        )

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners in GitHub.

        Args:
            runners: list of runners to delete.
        """
        for runner in runners:
            self._client.delete_runner(self._path, runner.id)

    def get_runner_token(
        self, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token and the runner.
        """
        return self._client.get_runner_registration_jittoken(self._path, instance_id, labels)

    def get_removal_token(self) -> str:
        """Get removal token from GitHub.

        This token is used for removing self-hosted runners.

        Returns:
            The removal token.
        """
        return self._client.get_runner_remove_token(self._path)

    def check_job_been_picked_up(self, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.

        Returns:
            True if the job has been picked up, False otherwise.
        """
        # job_url has the format:
        # "https://api.github.com/repos/cbartz/gh-runner-test/actions/jobs/22428484402"
        path = job_url.path
        # we know that path is not empty as it is validated by the JobDetails model
        job_url_path_parts = path.split("/")  # type: ignore
        job_id = job_url_path_parts[-1]
        owner = job_url_path_parts[2]
        repo = job_url_path_parts[3]
        logging.debug(
            "Parsed job_id: %s, owner: %s, repo: %s from job_url path %s",
            job_id,
            owner,
            repo,
            path,
        )

        # See response format:
        # https://docs.github.com/en/rest/actions/workflow-jobs?apiVersion=2022-11-28#get-a-job-for-a-workflow-run

        job_info = self._client.get_job_info(
            path=GitHubRepo(owner=owner, repo=repo), job_id=job_id
        )
        return job_info.status in [*JobPickedUpStates]

    @staticmethod
    def _is_runner_in_state(runner: SelfHostedRunner, states: set[PlatformRunnerState]) -> bool:
        """Check that the runner is in one of the states provided.

        Args:
            runner: Runner to filter.
            states: States in which to check the runner belongs to.

        Returns:
            True if the runner is in one of the state, else false.
        """
        return PlatformRunnerState.from_runner(runner) in states


class JobPickedUpStates(str, Enum):
    """The states of a job that indicate it has been picked up.

    Attributes:
        COMPLETED: The job has completed.
        IN_PROGRESS: The job is in progress.
    """

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
