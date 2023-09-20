#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Models and functions for the metric events."""

from pydantic import BaseModel, conint


class Event(BaseModel):
    """Base class for metric events.

    Attrs:
         timestamp: The UNIX time stamp of the time at which the event was originally issued.
    """

    timestamp: conint(ge=0)


class RunnerInstalled(Event):
    """Metric event for when a runner is installed.

    Attrs:
        flavor: Describes the characteristics of the runner.
          The flavour could be for example "small".
        duration: The duration of the installation in seconds.
    """

    flavor: str
    duration: conint(ge=0)


def issue_event(event: Event) -> None:
    """Transmit an event to Promtail.

    Args:
        event: The metric event to log.
    """
