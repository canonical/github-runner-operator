#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Package for platform providers."""
from enum import Enum


class Platform(str, Enum):
    """Enum for supported platforms.

    Attributes:
        GITHUB: GitHub platform.
        JOBMANAGER: JobManager platform.
        MULTIPLEXER: Multiplexer platform that uses several providers simultaneously.
    """

    GITHUB = "github"
    JOBMANAGER = "jobmanager"
    MULTIPLEXER = "multiplexer"
