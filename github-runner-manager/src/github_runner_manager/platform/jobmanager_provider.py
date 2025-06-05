# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""JobManager platform provider."""

import logging
from enum import Enum

import jobmanager_client
from jobmanager_client.rest import ApiException, NotFoundException
from pydantic import HttpUrl
from pydantic.error_wrappers import ValidationError
from urllib3.exceptions import RequestError

from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
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
    SelfHostedRunnerLabel,
)

logger = logging.getLogger(__name__)


class JobManagerPlatform(PlatformProvider):
    """Manage self-hosted runner on the JobManager."""

    def __init__(self, url: str):
        """Construct the object.

        Args:
            url: The jobmanager base URL.
        """
        self._url = url

    @classmethod
    def build(cls, jobmanager_configuration: JobManagerConfiguration) -> "JobManagerPlatform":
        """Build a new instance of the JobManagerPlatform.

        Args:
            jobmanager_configuration: Configuration for the jobmanager.

        Returns:
            New JobManagerPlatform.
        """
        return cls(url=jobmanager_configuration.url)

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
        configuration = jobmanager_client.Configuration(host=runner_identity.metadata.url)
        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.RunnersApi(api_client)
            try:
                response = api_instance.get_runner_health_v1_runner_runner_id_health_get(
                    int(runner_identity.metadata.runner_id)
                )
            except NotFoundException:
                # Pending to test with the real JobManager.
                # The last assumption is that the builder-agent did not contact
                # the JobManager and so it returns a 404.
                return PlatformRunnerHealth(
                    identity=runner_identity,
                    online=False,
                    deletable=False,
                    busy=False,
                )
            except (ApiException, RequestError, ValidationError) as exc:
                logger.exception(
                    "Error calling jobmanager api for runner %s. %s", runner_identity, exc
                )
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
        configuration = jobmanager_client.Configuration(host=self._url)
        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.RunnersApi(api_client)
            try:
                # Retrieve jobs
                # TODO: Ask for removal of series and arch in openapi spec
                runner_register_request = (
                    jobmanager_client.RegisterRunnerV1RunnerRegisterPostRequest(
                        name=instance_id.name, series="foobar", arch="foobar", labels=labels
                    )
                )

                response = api_instance.register_runner_v1_runner_register_post(
                    runner_register_request
                )
                if not response.id:
                    raise PlatformApiError("No runner ID from jobmanager API")
                updated_metadata = RunnerMetadata(
                    platform_name=metadata.platform_name, url=self._url
                )
                updated_metadata.runner_id = str(response.id)
                if token := response.token:
                    jobmanager_endpoint = (
                        f"{self._url}/v1/runner/{updated_metadata.runner_id}/health"
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
                            labels=[SelfHostedRunnerLabel(name=label) for label in labels],
                            status=GitHubRunnerStatus.OFFLINE,
                        ),
                    )
                raise PlatformApiError("Empty token from jobmanager API")
            except (ApiException, RequestError, ValidationError) as exc:
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
        configuration = jobmanager_client.Configuration(host=self._url)
        #
        # job_url has the path:
        # "/v1/job/<job_id>/health"
        path = job_url.path
        # we know that path is not empty as it is validated by the JobDetails model
        job_url_path_parts = path.split("/")  # type: ignore
        job_id = job_url_path_parts[-2]
        logging.debug(
            "Parsed job_id: %s from job_url path %s",
            job_id,
            path,
        )

        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.JobsApi(api_client)
            try:
                job = api_instance.get_health_v1_jobs_job_id_health_get(int(job_id))
                # the api returns a generic object, ignore the type for status
                if job.status != JobStatus.PENDING:  # type: ignore
                    return True
            except (ApiException, RequestError, ValidationError) as exc:
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


class JobStatus(str, Enum):
    """Status of a job on the JobManager.

    Attributes:
        IN_PROGRESS: Represents a job that is in progress.
        PENDING: Represents a job that is pending.
    """

    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
