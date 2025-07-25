# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client.

Migrate to PyGithub in the future. PyGithub is still lacking some API such as get runner groups.
"""
import functools
import logging
from datetime import datetime
from typing import Callable, ParamSpec, TypeVar
from urllib.error import HTTPError, URLError

import requests

# These exceptions are not found by pylint
from fastcore.net import (  # pylint: disable=no-name-in-module
    HTTP404NotFoundError,
    HTTP422UnprocessableEntityError,
)
from ghapi.all import GhApi, pages
from ghapi.page import paged
from requests import RequestException
from typing_extensions import assert_never

from github_runner_manager.configuration.github import GitHubOrg, GitHubPath, GitHubRepo
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.platform.platform_provider import (
    DeleteRunnerBusyError,
    JobNotFoundError,
    PlatformApiError,
    TokenError,
)
from github_runner_manager.types_.github import JITConfig, JobInfo, SelfHostedRunner

logger = logging.getLogger(__name__)

TIMEOUT_IN_SECS = 60


class GithubRunnerNotFoundError(Exception):
    """Represents an error when the runner could not be found on GitHub."""


# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")


def catch_http_errors(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
    """Catch HTTP errors and raise custom exceptions.

    Args:
        func: The target function to catch common errors for.

    Returns:
        The decorated function.
    """

    @functools.wraps(func)
    def wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        """Catch common errors when using the GitHub API.

        Args:
            args: Placeholder for positional arguments.
            kwargs: Placeholder for keyword arguments.

        Raises:
            TokenError: If there was an error with the provided token.
            PlatformApiError: If there was an unexpected error using the GitHub API.

        Returns:
            The decorated function.
        """
        try:
            return func(*args, **kwargs)
        # The ghapi module uses urllib. The HTTPError and URLError are urllib exceptions.
        except HTTPError as exc:
            if exc.code in (401, 403):
                if exc.code == 401:
                    msg = "Invalid token."
                else:
                    msg = "Provided token has not enough permissions or has reached rate-limit."
                raise TokenError(msg) from exc
            logger.warning("Error in GitHub request: %s", exc)
            raise PlatformApiError from exc
        except URLError as exc:
            logger.warning("General error in GitHub request: %s", exc)
            raise PlatformApiError from exc
        except RequestException as exc:
            logger.warning("Error in GitHub request: %s", exc)
            raise PlatformApiError from exc
        except TimeoutError as exc:
            logger.warning("Timeout in GitHub request: %s", exc)
            raise PlatformApiError from exc

    return wrapper


class GithubClient:
    """GitHub API client."""

    def __init__(self, token: str):
        """Instantiate the GiHub API client.

        Args:
            token: GitHub personal token for API requests.
        """
        self._token = token
        self._client = GhApi(token=self._token)

    @catch_http_errors
    def get_runner(self, path: GitHubPath, prefix: str, runner_id: int) -> SelfHostedRunner:
        """Get a specific self-hosted runner information under a repo or org.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            prefix: Build the InstanceID with this prefix.
            runner_id: Runner id to get the self hosted runner.

        Raises:
            GithubRunnerNotFoundError: If the runner is not found.

        Returns:
            The information for the requested runner.
        """
        try:
            if isinstance(path, GitHubRepo):
                raw_runner = self._client.actions.get_self_hosted_runner_for_repo(
                    path.owner, path.repo, runner_id, timeout=TIMEOUT_IN_SECS
                )
            else:
                raw_runner = self._client.actions.get_self_hosted_runner_for_org(
                    path.org, runner_id, timeout=TIMEOUT_IN_SECS
                )
        except HTTP404NotFoundError as err:
            raise GithubRunnerNotFoundError from err
        instance_id = InstanceID.build_from_name(prefix, raw_runner["name"])
        return SelfHostedRunner.build_from_github(raw_runner, instance_id)

    @catch_http_errors
    def list_runners(self, path: GitHubPath, prefix: str) -> list[SelfHostedRunner]:
        """Get all runners information on GitHub under a repo or org.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            prefix: Filter instances related to this prefix and build the InstanceID.

        Returns:
            List of runner information.
        """
        remote_runners_list: list[SelfHostedRunner] = []

        if isinstance(path, GitHubRepo):
            # The documentation of ghapi for pagination is incorrect and examples will give errors.
            # This workaround is a temp solution. Will be moving to PyGitHub in the future.
            self._client.actions.list_self_hosted_runners_for_repo(
                owner=path.owner, repo=path.repo, per_page=100
            )
            num_of_pages = self._client.last_page()
            remote_runners_list = [
                item
                for page in pages(
                    self._client.actions.list_self_hosted_runners_for_repo,
                    num_of_pages + 1,
                    owner=path.owner,
                    repo=path.repo,
                    per_page=100,
                    timeout=TIMEOUT_IN_SECS,
                )
                for item in page["runners"]
            ]
        if isinstance(path, GitHubOrg):
            # The documentation of ghapi for pagination is incorrect and examples will give errors.
            # This workaround is a temp solution. Will be moving to PyGitHub in the future.
            self._client.actions.list_self_hosted_runners_for_org(org=path.org, per_page=100)
            num_of_pages = self._client.last_page()
            remote_runners_list = [
                item
                for page in pages(
                    self._client.actions.list_self_hosted_runners_for_org,
                    num_of_pages + 1,
                    org=path.org,
                    per_page=100,
                    timeout=TIMEOUT_IN_SECS,
                )
                for item in page["runners"]
            ]

        # Filter by prefix and create the SelfHostedRunner instances.
        managed_runners_list = []
        for runner in remote_runners_list:
            if InstanceID.name_has_prefix(prefix, runner["name"]):
                instance_id = InstanceID.build_from_name(prefix, runner["name"])
                managed_runner = SelfHostedRunner.build_from_github(runner, instance_id)
                managed_runners_list.append(managed_runner)
        return managed_runners_list

    @catch_http_errors
    def get_runner_registration_jittoken(
        self, path: GitHubPath, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get token from GitHub used for registering runners.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            instance_id: Instance ID of the runner.
            labels: Labels for the runner.

        Returns:
            The registration token.
        """
        token: JITConfig
        if isinstance(path, GitHubRepo):
            # The supposition is that the runner_group_id 1 is the default.
            # If the repo does not belong to an org, there is no way to get the runner_group_id.
            token = self._client.actions.generate_runner_jitconfig_for_repo(
                owner=path.owner,
                repo=path.repo,
                name=instance_id.name,
                runner_group_id=1,
                labels=labels,
                timeout=TIMEOUT_IN_SECS,
            )
        elif isinstance(path, GitHubOrg):
            # We cannot cache it in here, as we are running in a forked process.
            # Pending to review.
            runner_group_id = self._get_runner_group_id(path)
            token = self._client.actions.generate_runner_jitconfig_for_org(
                org=path.org,
                name=instance_id.name,
                runner_group_id=runner_group_id,
                labels=labels,
                timeout=TIMEOUT_IN_SECS,
            )
        else:
            assert_never(token)

        runner = SelfHostedRunner.build_from_github(token["runner"], instance_id)
        return token["encoded_jit_config"], runner

    def _get_runner_group_id(self, org: GitHubOrg) -> int:
        """Get runner_group_id from group name for an org.

        Once this function is implemented in the ghapi library, we should
        use that instead. See https://github.com/AnswerDotAI/ghapi/issues/189.

        No pagination is used, so if there are more than 100 groups, this
        function could fail.
        """
        url = f"https://api.github.com/orgs/{org.org}/actions/runner-groups?per_page=100"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.get(url, headers=headers, timeout=TIMEOUT_IN_SECS)
        response.raise_for_status()
        data = response.json()
        try:
            for group in data["runner_groups"]:
                if group["name"] == org.group:
                    return group["id"]
        except TypeError as exc:
            raise PlatformApiError(f"Cannot get runner_group_id for group {org.group}.") from exc
        raise PlatformApiError(
            f"Cannot get runner_group_id for group {org.group}."
            " The group does not exist or there are more than 100 groups."
        )

    @catch_http_errors
    def delete_runner(self, path: GitHubPath, runner_id: int) -> None:
        """Delete the self-hosted runner from GitHub.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            runner_id: Id of the runner.

        Raises:
            DeleteRunnerBusyError: Error raised when trying to delete a runner that is online
                and busy.
        """
        try:
            if isinstance(path, GitHubRepo):
                self._client.actions.delete_self_hosted_runner_from_repo(
                    owner=path.owner,
                    repo=path.repo,
                    runner_id=runner_id,
                    timeout=TIMEOUT_IN_SECS,
                )
            else:
                self._client.actions.delete_self_hosted_runner_from_org(
                    org=path.org,
                    runner_id=runner_id,
                    timeout=TIMEOUT_IN_SECS,
                )
        # The function delete_self_hosted_runner fails in GitHub if the runner does not exist,
        # so we do not have to worry about that.
        except HTTP422UnprocessableEntityError as err:
            raise DeleteRunnerBusyError from err

    def get_job_info_by_runner_name(
        self, path: GitHubRepo, workflow_run_id: str, runner_name: str
    ) -> JobInfo:
        """Get information about a job for a specific workflow run identified by the runner name.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>'.
            workflow_run_id: Id of the workflow run.
            runner_name: Name of the runner.

        Raises:
            TokenError: if there was an error with the Github token credential provided.
            JobNotFoundError: If no jobs were found.

        Returns:
            Job information.
        """
        paged_kwargs = {
            "owner": path.owner,
            "repo": path.repo,
            "run_id": workflow_run_id,
            "timeout": 60,
        }
        try:
            for wf_run_page in paged(
                self._client.actions.list_jobs_for_workflow_run, **paged_kwargs
            ):
                jobs = wf_run_page["jobs"]
                # ghapi performs endless pagination,
                # so we have to break out of the loop if there are no more jobs
                if not jobs:
                    break
                for job in jobs:
                    if job["runner_name"] == runner_name:
                        return self._to_job_info(job)

        except HTTPError as exc:
            if exc.code in (401, 403):
                raise TokenError from exc
            raise JobNotFoundError(
                f"Could not find job for runner {runner_name}. "
                f"Could not list jobs for workflow run {workflow_run_id}"
            ) from exc

        raise JobNotFoundError(f"Could not find job for runner {runner_name}.")

    @catch_http_errors
    def get_job_info(self, path: GitHubRepo, job_id: str) -> JobInfo:
        """Get information about a job identified by the job id.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>'.
            job_id: The job id.

        Raises:
            JobNotFoundError: Cannot find job on GitHub.

        Returns:
            The JSON response from the API.
        """
        try:
            job_raw = self._client.actions.get_job_for_workflow_run(
                owner=path.owner,
                repo=path.repo,
                job_id=job_id,
                timeout=TIMEOUT_IN_SECS,
            )
        except HTTPError as exc:
            if exc.code == 404:
                raise JobNotFoundError(f"Could not find job for job id {job_id}.") from exc
            raise
        return self._to_job_info(job_raw)

    @staticmethod
    def _to_job_info(job: dict) -> JobInfo:
        """Convert the job dict to JobInfo.

        Args:
            job: The job dict.

        Returns:
            The JobInfo object.
        """
        # datetime strings should be in ISO 8601 format, but they can also use Z instead of +00:00,
        # which is not supported by datetime.fromisoformat
        created_at = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
        started_at = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        # conclusion could be null per api schema, so we need to handle that,
        # though we would assume that it should always be present, as the job should be finished.
        conclusion = job.get("conclusion", None)

        status = job["status"]
        job_id = job["id"]
        return JobInfo(
            job_id=job_id,
            created_at=created_at,
            started_at=started_at,
            conclusion=conclusion,
            status=status,
        )
