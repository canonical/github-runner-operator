# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client."""

import functools
import logging
from datetime import datetime
from typing import Callable, ParamSpec, TypeVar

from github import BadCredentialsException, Github, GithubException, UnknownObjectException
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

# Timeout in seconds for all PyGithub HTTP calls.
TIMEOUT_IN_SECS = 5 * 60


class GithubRunnerNotFoundError(Exception):
    """Represents an error when the runner could not be found on GitHub."""


# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")  # pylint: disable=invalid-name
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
        except BadCredentialsException as exc:
            raise TokenError("Invalid token.") from exc
        except GithubException as exc:
            if exc.status == 403:
                raise TokenError(
                    "Provided token has not enough permissions or has reached rate-limit."
                ) from exc
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
        self._github = Github(login_or_token=self._token, timeout=TIMEOUT_IN_SECS)
        # PyGithub lacks methods for some endpoints (repo-level JIT config, get job by ID,
        # runner groups). Use the internal requester for raw REST calls that still inherit
        # auth and timeout from the client.
        self._requester = self._github._Github__requester  # type: ignore[attr-defined]  # pylint: disable=protected-access  # noqa: E501

    @staticmethod
    def _pygithub_runner_to_dict(runner: object) -> dict:
        """Convert a PyGithub SelfHostedActionsRunner to a dict for build_from_github.

        Args:
            runner: PyGithub runner object.

        Returns:
            A dict compatible with SelfHostedRunner.build_from_github().
        """
        return {
            "id": runner.id,  # type: ignore[attr-defined]
            "name": runner.name,  # type: ignore[attr-defined]
            "os": runner.os,  # type: ignore[attr-defined]
            "status": runner.status,  # type: ignore[attr-defined]
            "busy": runner.busy,  # type: ignore[attr-defined]
            "labels": [
                {"id": label["id"], "name": label["name"], "type": label["type"]}
                for label in runner.labels()  # type: ignore[attr-defined]
            ],
        }

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
                runner = self._github.get_repo(f"{path.owner}/{path.repo}").get_self_hosted_runner(
                    runner_id
                )
            else:
                runner = self._github.get_organization(path.org).get_self_hosted_runner(runner_id)
        except UnknownObjectException as err:
            raise GithubRunnerNotFoundError from err
        raw_runner = self._pygithub_runner_to_dict(runner)
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
        if isinstance(path, GitHubRepo):
            runners = self._github.get_repo(f"{path.owner}/{path.repo}").get_self_hosted_runners()
        else:
            runners = self._github.get_organization(path.org).get_self_hosted_runners()

        managed_runners_list = []
        for runner in runners:
            raw_runner = self._pygithub_runner_to_dict(runner)
            if InstanceID.name_has_prefix(prefix, raw_runner["name"]):
                instance_id = InstanceID.build_from_name(prefix, raw_runner["name"])
                managed_runner = SelfHostedRunner.build_from_github(raw_runner, instance_id)
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
            _headers, token = self._requester.requestJsonAndCheck(
                "POST",
                f"/repos/{path.owner}/{path.repo}/actions/runners/generate-jitconfig",
                input={"name": instance_id.name, "runner_group_id": 1, "labels": labels},
            )
        elif isinstance(path, GitHubOrg):
            runner_group_id = self._get_runner_group_id(path)
            _headers, token = self._requester.requestJsonAndCheck(
                "POST",
                f"/orgs/{path.org}/actions/runners/generate-jitconfig",
                input={
                    "name": instance_id.name,
                    "runner_group_id": runner_group_id,
                    "labels": labels,
                },
            )
        else:
            assert_never(token)

        runner = SelfHostedRunner.build_from_github(token["runner"], instance_id)
        return token["encoded_jit_config"], runner

    def _get_runner_group_id(self, org: GitHubOrg) -> int:
        """Get runner_group_id from group name for an org.

        No pagination is used, so if there are more than 100 groups, this
        function could fail.
        """
        _headers, data = self._requester.requestJsonAndCheck(
            "GET",
            f"/orgs/{org.org}/actions/runner-groups",
            parameters={"per_page": 100},
        )
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
                self._github.get_repo(f"{path.owner}/{path.repo}").remove_self_hosted_runner(
                    runner_id
                )
            else:
                self._github.get_organization(path.org).delete_self_hosted_runner(runner_id)
        except GithubException as err:
            if err.status == 422:
                raise DeleteRunnerBusyError from err
            raise

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
        try:
            page = 1
            while True:
                _headers, data = self._requester.requestJsonAndCheck(
                    "GET",
                    f"/repos/{path.owner}/{path.repo}/actions/runs/{workflow_run_id}/jobs",
                    parameters={"per_page": 30, "page": page},
                )
                jobs = data["jobs"]
                if not jobs:
                    break
                for job in jobs:
                    if job["runner_name"] == runner_name:
                        return self._to_job_info(job)
                page += 1
        except GithubException as exc:
            if exc.status in (401, 403):
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
            _headers, job_raw = self._requester.requestJsonAndCheck(
                "GET",
                f"/repos/{path.owner}/{path.repo}/actions/jobs/{job_id}",
            )
        except UnknownObjectException as exc:
            raise JobNotFoundError(f"Could not find job for job id {job_id}.") from exc
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
        # conclusion could be null or an empty dictionary per api schema, so we need to handle
        # that though we would assume that it should always be present, as the job should be
        # finished.
        conclusion = job.get("conclusion", None) or None

        status = job["status"]
        job_id = job["id"]
        return JobInfo(
            job_id=job_id,
            created_at=created_at,
            started_at=started_at,
            conclusion=conclusion,
            status=status,
        )
