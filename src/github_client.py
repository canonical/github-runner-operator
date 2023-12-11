# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client.

Migrate to PyGithub in the future. PyGithub is still lacking some API such as
remove token for runner.
"""

import logging

from ghapi.all import GhApi, pages
from requests import Session
from typing_extensions import assert_never

from github_type import RegistrationToken, RemoveToken, RunnerApplicationList, SelfHostedRunner
from runner_type import GithubOrg, GithubPath, GithubRepo

logger = logging.getLogger(__name__)


class GithubClient:
    """GitHub API client."""

    def __init__(self, token: str, request_session: Session):
        """Instantiate the GiHub API client.

        Args:
            token: GitHub personal token for API requests.
            request_session: Requests session for HTTP requests.
        """
        self._token = token
        self._client = GhApi(token=self._token)
        self._session = request_session

    def get_runner_applications(self, path: GithubPath) -> RunnerApplicationList:
        """Get list of runner applications available for download.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
        Returns:
            List of runner applications.
        """
        runner_bins: RunnerApplicationList = []
        if isinstance(path, GithubRepo):
            runner_bins = self._client.actions.list_runner_applications_for_repo(
                owner=path.owner, repo=path.repo
            )
        if isinstance(path, GithubOrg):
            runner_bins = self._client.actions.list_runner_applications_for_org(org=path.org)

        return runner_bins

    def get_runner_github_info(self, path: GithubPath) -> list[SelfHostedRunner]:
        """Get runner information on GitHub under a repo or org.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.

        Returns:
            List of runner information.
        """
        remote_runners_list: list[SelfHostedRunner] = []

        if isinstance(path, GithubRepo):
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
        if isinstance(path, GithubOrg):
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

    def get_runner_remove_token(self, path: GithubPath) -> str:
        """Get token from GitHub used for removing runners.

        Returns:
            The removing token.
        """
        token: RemoveToken
        if isinstance(path, GithubRepo):
            token = self._client.actions.create_remove_token_for_repo(
                owner=path.owner, repo=path.repo
            )
        elif isinstance(path, GithubOrg):
            token = self._client.actions.create_remove_token_for_org(org=path.org)
        else:
            assert_never(token)

        return token["token"]

    def get_runner_registration_token(self, path: GithubPath) -> str:
        """Get token from GitHub used for registering runners.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.

        Returns:
            The registration token.
        """
        token: RegistrationToken
        if isinstance(path, GithubRepo):
            token = self._client.actions.create_registration_token_for_repo(
                owner=path.owner, repo=path.repo
            )
        elif isinstance(path, GithubOrg):
            token = self._client.actions.create_registration_token_for_org(org=path.org)
        else:
            assert_never(token)

        return token["token"]

    def delete_runner(self, path: GithubPath, runner_id: int) -> None:
        """Delete the self-hosted runner from GitHub.

        Args:
            path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
                name.
            runner_id: Id of the runner.
        """
        if isinstance(path, GithubRepo):
            self._client.actions.delete_self_hosted_runner_from_repo(
                owner=path.owner,
                repo=path.repo,
                runner_id=runner_id,
            )
        if isinstance(path, GithubOrg):
            self._client.actions.delete_self_hosted_runner_from_org(
                org=path.org,
                runner_id=runner_id,
            )
