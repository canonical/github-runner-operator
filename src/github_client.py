# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client.

Migrate to PyGithub in the future. PyGithub is still lacking some API such as
remove token for runner.
"""
import logging
from typing import ParamSpec, TypeVar

from github_runner_manager.github_client import GithubClient as GitHubRunnerManagerGitHubClient
from github_runner_manager.github_client import catch_http_errors
from github_runner_manager.types_.github import (
    GitHubOrg,
    GitHubPath,
    GitHubRepo,
    RunnerApplication,
    RunnerApplicationList,
)

from charm_state import Arch
from errors import RunnerBinaryError

logger = logging.getLogger(__name__)

# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")


class GithubClient(GitHubRunnerManagerGitHubClient):
    """GitHub API client."""

    @catch_http_errors
    def get_runner_application(
        self, path: GitHubPath, arch: Arch, os: str = "linux"
    ) -> RunnerApplication:
        """Get runner application available for download for given arch.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            arch: The runner architecture.
            os: The operating system that the runner binary should run on.

        Raises:
            RunnerBinaryError: If the runner application for given architecture and OS is not
                found.

        Returns:
            The runner application.
        """
        runner_applications: RunnerApplicationList = []
        if isinstance(path, GitHubRepo):
            runner_applications = self._client.actions.list_runner_applications_for_repo(
                owner=path.owner, repo=path.repo
            )
        if isinstance(path, GitHubOrg):
            runner_applications = self._client.actions.list_runner_applications_for_org(
                org=path.org
            )
        logger.debug("Response of runner applications list: %s", runner_applications)
        try:
            return next(
                bin
                for bin in runner_applications
                if bin["os"] == os and bin["architecture"] == arch
            )
        except StopIteration as err:
            raise RunnerBinaryError(
                f"Unable query GitHub runner binary information for {os} {arch}"
            ) from err
