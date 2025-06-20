# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing GitHub Configuration."""

from typing import TypeAlias

from github_runner_manager.platform.platform_provider import PlatformConfiguration


class GitHubConfiguration(PlatformConfiguration):
    """GitHub configuration for the application.

    Attributes:
       token: GitHub Token.
       path: Information of the repository or organization.
    """

    token: str
    path: "GitHubPath"


class GitHubRepo(BaseModel):
    """Represent GitHub repository.

    Attributes:
        owner: Owner of the GitHub repository.
        repo: Name of the GitHub repository.
    """

    owner: str
    repo: str

    def path(self) -> str:
        """Return a string representing the path.

        Returns:
            Path to the GitHub entity.
        """
        return f"{self.owner}/{self.repo}"


class GitHubOrg(BaseModel):
    """Represent GitHub organization.

    Attributes:
        org: Name of the GitHub organization.
        group: Runner group to spawn the runners in.
    """

    org: str
    group: str

    def path(self) -> str:
        """Return a string representing the path.

        Returns:
            Path to the GitHub entity.
        """
        return self.org


GitHubPath: TypeAlias = GitHubOrg | GitHubRepo


def parse_github_path(path_str: str, runner_group: str) -> GitHubPath:
    """Parse GitHub path.

    Args:
        path_str: GitHub path in string format.
        runner_group: Runner group name for GitHub organization. If the path is
            a repository this argument is ignored.

    Raises:
        ValueError: if an invalid path string was given.

    Returns:
        GithubPath object representing the GitHub repository, or the GitHub
        organization with runner group information.
    """
    if "/" in path_str:
        paths = tuple(segment for segment in path_str.split("/") if segment)
        if len(paths) != 2:
            # TODO: create custom error
            raise ValueError(f"Invalid path configuration {path_str}")
        owner, repo = paths
        return GitHubRepo(owner=owner, repo=repo)
    return GitHubOrg(org=path_str, group=runner_group)


# For pydantic to work with forward references.
GitHubConfiguration.update_forward_refs()
