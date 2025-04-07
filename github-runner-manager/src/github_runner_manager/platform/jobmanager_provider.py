# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""TODO."""

from github_runner_manager.configuration.jobmanager import JobManagerConfiguration
from github_runner_manager.platform import platform_provider


# Work in progress.
class JobManagerPlatform(
    platform_provider.PlatformProvider
):  # pylint: disable=too-few-public-methods
    """TODO."""

    def __init__(self, prefix: str, jobmanager_configuration: JobManagerConfiguration):
        """Construct the object.

        Args:
            prefix: The prefix in the name to identify the runners managed by this instance.
            jobmanager_configuration: JobManager configuration information.

        Raises:
            NotImplementedError: Work in progress
        """
        self._prefix = prefix
        self._path = jobmanager_configuration.path
        raise NotImplementedError
