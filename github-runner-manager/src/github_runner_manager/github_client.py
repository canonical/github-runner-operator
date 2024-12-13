# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client.

Migrate to PyGithub in the future. PyGithub is still lacking some API such as
remove token for runner.
"""
import functools
import logging
from datetime import datetime
from typing import Callable, ParamSpec, TypeVar
from urllib.error import HTTPError

from ghapi.all import GhApi, pages
from ghapi.page import paged
from typing_extensions import assert_never

from github_runner_manager.errors import GithubApiError, JobNotFoundError, TokenError
from github_runner_manager.types_.github import (
    GitHubOrg,
    GitHubPath,
    GitHubRepo,
    JobInfo,
    RegistrationToken,
    RemoveToken,
    SelfHostedRunner,
)

logger = logging.getLogger(__name__)

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
            GithubApiError: If there was an unexpected error using the GitHub API.

        Returns:
            The decorated function.
        """
        try:
            return func(*args, **kwargs)
        except HTTPError as exc:
            if exc.code in (401, 403):
                if exc.code == 401:
                    msg = "Invalid token."
                else:
                    msg = "Provided token has not enough permissions or has reached rate-limit."
                raise TokenError(msg) from exc
            raise GithubApiError from exc

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
    def get_runner_github_info(self, path: GitHubPath) -> list[SelfHostedRunner]:
        """Get runner information on GitHub under a repo or org.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.

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
                )
                for item in page["runners"]
            ]
        return remote_runners_list

    @catch_http_errors
    def get_runner_remove_token(self, path: GitHubPath) -> str:
        """Get token from GitHub used for removing runners.

        Args:
            path: The Github org/repo path.

        Returns:
            The removing token.
        """
        token: RemoveToken
        if isinstance(path, GitHubRepo):
            token = self._client.actions.create_remove_token_for_repo(
                owner=path.owner, repo=path.repo
            )
        elif isinstance(path, GitHubOrg):
            token = self._client.actions.create_remove_token_for_org(org=path.org)
        else:
            assert_never(token)

        return token["token"]

    @catch_http_errors
    def get_runner_registration_token(self, path: GitHubPath) -> str:
        """Get token from GitHub used for registering runners.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.

        Returns:
            The registration token.
        """
        token: RegistrationToken
        if isinstance(path, GitHubRepo):
            token = self._client.actions.create_registration_token_for_repo(
                owner=path.owner, repo=path.repo
            )
        elif isinstance(path, GitHubOrg):
            token = self._client.actions.create_registration_token_for_org(org=path.org)
        else:
            assert_never(token)

        return token["token"]

    @catch_http_errors
    def delete_runner(self, path: GitHubPath, runner_id: int) -> None:
        """Delete the self-hosted runner from GitHub.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            runner_id: Id of the runner.
        """
        if isinstance(path, GitHubRepo):
            self._client.actions.delete_self_hosted_runner_from_repo(
                owner=path.owner,
                repo=path.repo,
                runner_id=runner_id,
            )
        if isinstance(path, GitHubOrg):
            self._client.actions.delete_self_hosted_runner_from_org(
                org=path.org,
                runner_id=runner_id,
            )

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
        paged_kwargs = {"owner": path.owner, "repo": path.repo, "run_id": workflow_run_id}
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

        Returns:
            The JSON response from the API.
        """
        job_raw = self._client.actions.get_job_for_workflow_run(
            owner=path.owner,
            repo=path.repo,
            job_id=job_id,
        )
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
