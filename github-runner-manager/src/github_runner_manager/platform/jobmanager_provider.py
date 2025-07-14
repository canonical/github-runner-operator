# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""JobManager platform provider."""

import logging

from pydantic import HttpUrl

from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
from github_runner_manager.jobmanager_api import (
    JobManagerAPI,
    JobManagerAPIError,
    JobManagerAPINotFoundError,
    JobStatus,
    RunnerStatus,
)
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformApiError,
    PlatformProvider,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import (
    GitHubRunnerStatus,
    SelfHostedRunner,
)

logger = logging.getLogger(__name__)


class JobManagerPlatform(PlatformProvider):
    """Manage self-hosted runner on the JobManager."""

    def __init__(self, jobmanager_api: JobManagerAPI):
        """Construct the object.

        Args:
            jobmanager_api: The jobmanager API client to use.
        """
        self._jobmanager_api = jobmanager_api

    @classmethod
    def build(cls, jobmanager_configuration: JobManagerConfiguration) -> "JobManagerPlatform":
        """Build a new instance of the JobManagerPlatform.

        Args:
            jobmanager_configuration: Configuration for the jobmanager.

        Returns:
            New JobManagerPlatform.
        """
        return cls(
            jobmanager_api=JobManagerAPI(
                url=jobmanager_configuration.url, token=jobmanager_configuration.token
            ),
        )

    def get_runner_health(
        self,
        runner_identity: RunnerIdentity,
    ) -> PlatformRunnerHealth:
        """Get health information on jobmanager runner.

        Args:
            runner_identity: Identity of the runner.

        Raises:
            PlatformApiError: If there was an error calling the jobmanager client.

        Returns:
           The health of the runner in the jobmanager.
        """
        try:
            response = self._jobmanager_api.get_runner_health(
                int(runner_identity.metadata.runner_id)
            )
        except JobManagerAPINotFoundError:
            return PlatformRunnerHealth(
                identity=runner_identity,
                online=False,
                deletable=False,
                busy=False,
            )
        except JobManagerAPIError as exc:
            logger.exception(
                "Error calling jobmanager api for runner %s. %s", runner_identity, exc
            )
            raise PlatformApiError("API error") from exc

        online = response.status != RunnerStatus.PENDING
        # busy is complex in the jobmanager, as a completed job that is not deletable is really
        # busy. As so, every job that is not deletable is considered busy.
        busy = not response.deletable
        deletable = response.deletable

        return PlatformRunnerHealth(
            identity=runner_identity,
            online=online,
            deletable=deletable,
            busy=busy,
        )

    def get_runners_health(self, requested_runners: list[RunnerIdentity]) -> RunnersHealthResponse:
        """Get the health of a list of requested runners.

        Args:
            requested_runners: List of requested runners.

        Returns:
            Health information on the runners.
        """
        runners_health = []
        failed_runners = []
        for identity in requested_runners:
            try:
                health = self.get_runner_health(identity)
            except PlatformApiError as exc:
                logger.warning(
                    "Failed to get information for the runner %s in the jobmanager. %s",
                    identity,
                    exc,
                )
                failed_runners.append(identity)
                continue
            runners_health.append(health)
        return RunnersHealthResponse(
            requested_runners=runners_health,
            failed_requested_runners=failed_runners,
        )

    def delete_runner(self, runner_identity: RunnerIdentity) -> None:
        """Delete a runner from jobmanager.

        This method does nothing, as the jobmanager does not implement it.

        Args:
            runner_identity: The identity of the runner to delete.
        """
        logger.debug("No need to delete runners in the jobmanager.")

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get the runner context for a self-hosted runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: Metadata for the runner.
            labels: Labels for the runner.

        Raises:
            PlatformApiError: Problem with the underlying API.

        Returns:
            A tuple containing the runner context and the self-hosted runner.
        """
        try:
            response = self._jobmanager_api.register_runner(name=instance_id.name, labels=labels)
            jobmanager_base_url = self._jobmanager_api.url.rstrip("/")
            updated_metadata = RunnerMetadata(
                platform_name=metadata.platform_name, url=jobmanager_base_url
            )
            updated_metadata.runner_id = str(response.id)
            if token := response.token:
                jobmanager_endpoint = (
                    f"{jobmanager_base_url}/v1/runners/{updated_metadata.runner_id}/health"
                )
                # For now, use the first label
                label = "undefined"
                if labels:
                    label = labels[0]
                command_to_run = (
                    f"BUILDER_LABEL={label} JOB_MANAGER_BEARER_TOKEN={token} "
                    f"JOB_MANAGER_API_ENDPOINT={jobmanager_endpoint} "
                    "builder-agent"
                )
                return (
                    RunnerContext(
                        shell_run_script=command_to_run,
                        ingress_tcp_ports=[8080],
                    ),
                    SelfHostedRunner(
                        identity=RunnerIdentity(
                            instance_id=instance_id,
                            metadata=metadata,
                        ),
                        busy=False,
                        id=int(updated_metadata.runner_id),
                        labels=labels,
                        status=GitHubRunnerStatus.OFFLINE,
                    ),
                )
            raise PlatformApiError("Empty token from jobmanager API")
        except JobManagerAPIError as exc:
            logger.exception("Error calling jobmanager api.")
            raise PlatformApiError("API error") from exc

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
            metadata: Metadata for the runner.

        Raises:
            PlatformApiError: Problem with the underlying client.
            ValueError: Raised when the job_url is malformed.

        Returns:
            True if the job has been picked up, False otherwise.
        """
        # job_url has the path:
        # "/v1/jobs/<job_id>"
        job_path_prefix = "/v1/jobs/"

        path = job_url.path
        if not (path and path.startswith(job_path_prefix)):
            logger.error(
                "Job URL path does not start with '%s'. Received %s", job_path_prefix, path
            )
            raise ValueError(f'Job URL path does not start with "{job_path_prefix}"')
        try:
            job_id = int(path[len(job_path_prefix) :])  # Extract job_id from the path
        except ValueError as exc:
            logger.error(
                "Job URL path %s does not contain a valid job_id after '%s'",
                path,
                job_path_prefix,
            )
            raise ValueError(
                f"Job URL path does not contain a valid job_id after '{job_path_prefix}'"
            ) from exc
        logging.debug(
            "Parsed job_id: %s from job_url path %s",
            job_id,
            path,
        )

        try:
            job = self._jobmanager_api.get_job(job_id)
            if job.status != JobStatus.PENDING:
                return True
        except JobManagerAPIError as exc:
            logger.exception("Error calling jobmanager api to get job information.")
            raise PlatformApiError("API error") from exc
        return False

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get the Job info from the provider.

        Args:
            metadata: Metadata for the runner.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.

        Raises:
            PlatformApiError: This is not provided by this interface yet.
        """
        raise PlatformApiError("get_job_info not provided by the jobmanager")
