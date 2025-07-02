#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing JobManager Configuration."""
from pydantic import BaseModel, HttpUrl


class JobManagerConfiguration(BaseModel):
    """JobManager configuration for the application.

    Attributes:
       url: Base url of the job manager API.
      token: Token to authenticate with the job manager API.
    """

    url: HttpUrl
    token: str
