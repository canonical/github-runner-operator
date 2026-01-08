# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factory for instantiating platform provider."""
from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.platform.github_provider import GitHubRunnerPlatform
from github_runner_manager.platform.platform_provider import PlatformProvider


def platform_factory(
    vm_prefix: str,
    github_config: GitHubConfiguration | None,
) -> PlatformProvider:
    """Instantiate a concrete Platform Provider.

    Args:
        vm_prefix: The prefix for the virtual machines to be created.
        github_config: Configuration of the GitHub instance.

    Raises:
        ValueError: If an invalid configuration has been passed.

    Returns:
        A concrete platform provider.
    """
    if not github_config:
        raise ValueError("Missing configuration.")
    return GitHubRunnerPlatform.build(prefix=vm_prefix, github_configuration=github_config)
