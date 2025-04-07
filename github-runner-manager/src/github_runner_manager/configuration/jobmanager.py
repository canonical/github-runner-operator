# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing JobManager Configuration."""

from pydantic import BaseModel


class JobManagerConfiguration(BaseModel):
    """JobManager configuration for the application.

    Attributes:
       url: URL of the JobManager.
    """

    url: str
