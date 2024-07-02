# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Data types used by modules handling metrics."""

from typing import NamedTuple, Optional

from github_type import JobConclusion


class GithubJobMetrics(NamedTuple):
    """Metrics about a job.

    Attributes:
        queue_duration: The time in seconds the job took before the runner picked it up.
        conclusion: The conclusion of the job.
    """

    queue_duration: float
    conclusion: Optional[JobConclusion]
