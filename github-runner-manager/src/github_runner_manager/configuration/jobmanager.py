#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module containing GitHub Configuration."""
from pydantic import BaseModel, HttpUrl


class JobManagerConfiguration(BaseModel):
    """GitHub configuration for the application.

    Attributes:
       url: Base url of the job manager API.
    """

    url: HttpUrl
