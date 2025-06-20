# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for managing self-hosted runner on GitHub side."""

import logging
from enum import Enum

from pydantic import HttpUrl

from github_runner_manager.configuration.github import GitHubConfiguration, GitHubRepo
from github_runner_manager.github_client import GithubClient, GithubRunnerNotFoundError
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerHealth,
    PlatformRunnerStatus,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner

logger = logging.getLogger(__name__)


class GitHubRunnerPlatform(PlatformProvider):
    """Manage self-hosted runner on GitHub side."""

    def __init__(self, prefix: str, path: str, github_client: GithubClient):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            path: GitHub path.
            github_client: GitHub client.
        """
        self._prefix = prefix
        self._path = path
        self._client = github_client

    @classmethod
    def build(
        cls, prefix: str, github_configuration: GitHubConfiguration
    ) -> "GitHubRunnerPlatform":
        """Build a GitHubRunnerPlatform.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            github_configuration: GitHub configuration

        Returns:
            A new GitHubRunnerPlatform.
        """
        return cls(
            prefix=prefix,
            path=github_configuration.path,
            github_client=GithubClient(github_configuration.token),
        )

    def get_runner_health(
        self,
        runner_identity: RunnerIdentity,
    ) -> PlatformRunnerHealth:
        """Get information on the health of a list of github runners.

        Args:
            runner_identity: Identity for the runner.

        Returns:
            Information about the health status of the runner.
        """
        try:
            runner = self._client.get_runner(
                self._path, self._prefix, int(runner_identity.metadata.runner_id)
            )
            online = runner.status == GitHubRunnerStatus.ONLINE
            return PlatformRunnerHealth(
                identity=runner_identity,
                online=online,
                busy=runner.busy,
                deletable=False,
            )

        except GithubRunnerNotFoundError:
            return PlatformRunnerHealth(
                identity=runner_identity,
                online=False,
                busy=False,
                deletable=True,
                runner_in_platform=False,
            )

    def get_runners_health(self, requested_runners: list[RunnerIdentity]) -> RunnersHealthResponse:
        """Get the health of a list of requested runners.

        Args:
            requested_runners: List of requested runners.

        Returns:
            Health information on the runners.
        """
        requested_runners_health = []
        github_runners = self._client.list_runners(self._path, self._prefix)
        github_runners_map = {runner.identity.instance_id: runner for runner in github_runners}
        for identity in requested_runners:
            if identity.instance_id in github_runners_map:
                github_runner = github_runners_map[identity.instance_id]
                online = github_runner.status == GitHubRunnerStatus.ONLINE
                requested_runners_health.append(
                    PlatformRunnerHealth(
                        identity=identity,
                        online=online,
                        busy=github_runner.busy,
                        deletable=False,
                    )
                )
            else:
                # A runner not found in GitHub is a runner considered deletable.
                requested_runners_health.append(
                    PlatformRunnerHealth(
                        identity=identity,
                        online=False,
                        busy=False,
                        deletable=True,
                        runner_in_platform=False,
                    )
                )

        # Now the other way. Get all runners in GitHub that are not in the requested runners
        requested_instance_ids = {runner.instance_id for runner in requested_runners}
        non_requested_runners = [
            runner.identity
            for runner in github_runners
            if runner.identity.instance_id not in requested_instance_ids
        ]
        return RunnersHealthResponse(
            requested_runners=requested_runners_health,
            non_requested_runners=non_requested_runners,
        )

    def delete_runner(self, runner_identity: RunnerIdentity) -> None:
        """Delete a runner from GitHub.

        This method will raise DeleteRunnerBusyError if the runner is not deletable, that is,
        if it is busy. If the runner does not exist it will not fail.

        Args:
            runner_identity: Identity of the runner to delete.
        """
        logger.info("Delete runner in GitHub: %s", runner_identity)
        self._client.delete_runner(self._path, int(runner_identity.metadata.runner_id))

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get registration JIT token from GitHub.

        This token is used for registering self-hosted runners.

        Args:
            metadata: Metadata for the runner.
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token and the runner.
        """
        token, runner = self._client.get_runner_registration_jittoken(
            self._path, instance_id, labels
        )
        command_to_run = (
            "su - ubuntu -c "
            f'"cd ~/actions-runner && /home/ubuntu/actions-runner/run.sh --jitconfig {token} --name {name}"'
        )
        return RunnerContext(shell_run_script=command_to_run), runner

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            metadata: Metadata for the runner.
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

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get the Job info from the provider.

        Args:
            metadata: Metadata of the runner.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.

        Returns:
            Information about the Job.
        """
        owner, repo = repository.split("/", maxsplit=1)
        job_info = self._client.get_job_info_by_runner_name(
            path=GitHubRepo(owner=owner, repo=repo),
            workflow_run_id=workflow_run_id,
            runner_name=runner.name,
        )
        logger.debug(
            "Job info for runner %s with workflow run id %s: %s",
            runner,
            workflow_run_id,
            job_info,
        )
        return JobInfo(
            created_at=job_info.created_at,
            started_at=job_info.started_at,
            conclusion=job_info.conclusion,
        )

    @staticmethod
    def _is_runner_in_state(runner: SelfHostedRunner, states: set[PlatformRunnerStatus]) -> bool:
        """Check that the runner is in one of the states provided.

        Args:
            runner: Runner to filter.
            states: States in which to check the runner belongs to.

        Returns:
            True if the runner is in one of the state, else false.
        """
        return PlatformRunnerStatus.from_runner(runner) in states


class JobPickedUpStates(str, Enum):
    """The states of a job that indicate it has been picked up.

    Attributes:
        COMPLETED: The job has completed.
        IN_PROGRESS: The job is in progress.
    """

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
