#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Models and functions for the metric events."""


from pydantic import BaseModel, conint


class Event(BaseModel):
    """Base class for metric events."""
    event: str
    """The name of the event."""
    timestamp: conint(ge=0)
    """The UNIX timestamp of the event."""


class RunnerInstalled(Event):
    """Metric event for when a runner is installed."""
    event = "runner_installed"
    """The name of the event."""
    flavor: str
    """The flavor of the runner."""
    duration: conint(ge=0)
    """The duration of the installation in seconds."""


def issue_event(event: Event) -> None:
    """Transmit an event to Promtail.

    Args:
        event: The metric event to log.
    """
