#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Package for code implementing reactive scheduling."""
from pydantic import BaseModel, HttpUrl


class Job(BaseModel):
    """A job for which a runner is needed."""
    labels: list[str]
    github_run_url: HttpUrl
