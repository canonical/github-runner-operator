# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""GitHub API client.

Migrate to PyGithub in the future. PyGithub is still lacking some API such as
remove token for runner.
"""

import logging
import shutil
from zipfile import ZipFile

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

    def get_latest_artifact(
        self, owner: str, repo: str, artifact_name: str, filename: str, previous_url: str | None
    ) -> str:
        """Ensure the latest artifact from GitHub repo is downloaded.

        Args:
            owner: Owner of the GitHub repo.
            repo: Name of the GitHub repo.
            artifact_name: Name of the artifact to download.
            filename: Name of the file to decompress from the artifact.
            previous_url: Download URL of the previous download of artifact.

        Returns:
            Download URL of the latest artifact
        """
        # Get the last 2000 artifacts on the repository.
        artifacts = [
            item
            for page in pages(
                self._client.actions.list_artifacts_for_repo,
                20,
                owner=owner,
                repo=repo,
                per_page=100,
            )
            for item in page["artifacts"]
        ]

        artifact_infos = list(
            filter(lambda x: x.name == artifact_name and not x.expired, artifacts)
        )
        artifact_infos = sorted(artifact_infos, key=lambda x: x.created_at, reverse=True)
        artifact_info = next(iter(artifact_infos), None)
        if not artifact_info:
            raise RuntimeError(
                f"Unable to find non-expired {artifact_name} artifact at {owner}/{repo}"
            )

        if artifact_info.archive_download_url == previous_url:
            return previous_url

        logger.info(
            "Downloading lastest artifact %s created at %s",
            artifact_name,
            artifact_info.created_at,
        )

        # Download image zip to disk with buffer size 128MiB.
        with self._session.get(
            artifact_info.archive_download_url,
            headers={
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=60,
            stream=True,
        ) as response:
            with open(f"/home/ubuntu/{filename}.zip", "wb") as file:
                shutil.copyfileobj(response.raw, file, 128 * 1024)

        with ZipFile(f"/home/ubuntu/{filename}.zip", "r") as artifact_zip:
            artifact_zip.extract(filename)

        return artifact_info.archive_download_url
