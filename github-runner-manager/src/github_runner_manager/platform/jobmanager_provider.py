# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""JobManager platform provider."""

import logging
from enum import Enum

import jobmanager_client
from jobmanager_client.models.v1_jobs_job_id_token_post_request import V1JobsJobIdTokenPostRequest
from jobmanager_client.rest import ApiException
from pydantic import HttpUrl

from github_runner_manager.errors import PlatformApiError
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
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import (
    GitHubRunnerStatus,
    SelfHostedRunner,
    SelfHostedRunnerLabel,
)

logger = logging.getLogger(__name__)


# TODO GET ALL CONNECTION ERRORS AND SIMILAR AND TRANSFORM THEM TO A PROPER EXCEPTION
class JobManagerPlatform(PlatformProvider):
    """Manage self-hosted runner on the JobManager."""

    @classmethod
    def build(cls) -> "JobManagerPlatform":
        """Build a new instance of the JobManagerPlatform.

        Returns:
            New JobManagerPlatform.
        """
        return cls()

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
        logger.info("JAVI get runner health: %s", runner_identity.instance_id)
        configuration = jobmanager_client.Configuration(host=runner_identity.metadata.url)
        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.DefaultApi(api_client)
            try:
                response = api_instance.v1_jobs_job_id_health_get(
                    int(runner_identity.metadata.runner_id)
                )
                logger.info("JAVI get runner health response: %s", response)
            except ApiException as exc:
                logger.exception("Error calling jobmanager api.")
                raise PlatformApiError("API error") from exc

        # Valid values for status are: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
        # We should review the jobmanager for any change in their statuses.
        # Any other state besides PENDING means that no more waiting should be done
        # for the runner, so it is equivalent to online, although the jobmanager does
        # not provide an exact match with "online".
        online = response.status not in [JobStatus.PENDING]
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
        """TODO.

        Args:
            requested_runners: TODO

        Returns:
            Health information on the runners.
        """
        logger.info("JAVI get runners health: %s", requested_runners)
        runners_health = []
        for identity in requested_runners:
            health = self.get_runner_health(identity)
            runners_health.append(health)
        return RunnersHealthResponse(
            requested_runners=runners_health,
        )

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners.

        Args:
            runners: list of runners to delete.
        """
        # TODO for now do not do any work so the reconciliation can work.
        logger.info("jobmanager.delete_runners not implemented")

    def delete_runner(self, runner_identity: RunnerIdentity) -> None:
        """TODO.

        TODO can raise DeleteRunnerBusyError

        Args:
            runner_identity: TODO
        """
        logger.debug("No need to delete jobs in the jobmanager.")

    def get_runner_context(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[RunnerContext, SelfHostedRunner]:
        """Get a one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: Metadata for the runner.
            labels: Labels for the runner.

        Raises:
            PlatformApiError: Problem with the underlying API.

        Returns:
            New runner token.
        """
        configuration = jobmanager_client.Configuration(host=metadata.url)
        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.DefaultApi(api_client)
            try:
                # Retrieve jobs
                jobrequest = V1JobsJobIdTokenPostRequest(job_id=int(metadata.runner_id))
                response = api_instance.v1_jobs_job_id_token_post(
                    int(metadata.runner_id), jobrequest
                )
                if token := response.token:
                    jobmanager_endpoint = f"{metadata.url}/v1/jobs/{metadata.runner_id}/health"
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
                            id=int(metadata.runner_id),
                            labels=[SelfHostedRunnerLabel(name=label) for label in labels],
                            status=GitHubRunnerStatus.OFFLINE,
                        ),
                    )
                raise PlatformApiError("Empty token from jobmanager API")
            except ApiException as exc:
                logger.exception("Error calling jobmanager api.")
                raise PlatformApiError("API error") from exc

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
            metadata: Metadata for the runner.

        Raises:
            PlatformApiError: Problem with the underlying client.

        Returns:
            True if the job has been picked up, False otherwise.
        """
        configuration = jobmanager_client.Configuration(host=metadata.url)

        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.DefaultApi(api_client)
            try:
                job = api_instance.v1_jobs_job_id_get(int(metadata.runner_id))
                logger.exception("JAVI check_job_been_picked_up: %s", job)
                if job.status != JobStatus.PENDING:
                    return True
            except ApiException as exc:
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
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError


class JobStatus(str, Enum):
    """Status of a job on the JobManager.

    Attributes:
        IN_PROGRESS: Represents a job that is in progress.
        PENDING: Represents a job that is pending.
    """

    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
