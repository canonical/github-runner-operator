#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing JobManager Configuration."""
from pydantic import HttpUrl

from github_runner_manager.platform.platform_provider import PlatformConfiguration


class JobManagerConfiguration(PlatformConfiguration):
    """JobManager configuration for the application.

    Attributes:
       url: Base url of the job manager API.
    """

    url: HttpUrl
