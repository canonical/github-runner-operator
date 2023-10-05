#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Models and functions for the metric events."""
import json
import logging
from pathlib import Path

from pydantic import BaseModel, NonNegativeInt

METRICS_LOG_PATH = Path("/var/log/github-runner-metrics.log")

logger = logging.getLogger(__name__)


class Event(BaseModel):
    """Base class for metric events.

    Attrs:
         timestamp: The UNIX time stamp of the time at which the event was originally issued.
    """

    timestamp: NonNegativeInt


class RunnerInstalled(Event):
    """Metric event for when a runner is installed.

    Attrs:
        flavor: Describes the characteristics of the runner.
          The flavour could be for example "small".
        duration: The duration of the installation in seconds.
    """

    flavor: str
    duration: NonNegativeInt


def _camel_to_snake(camel_case_string: str) -> str:
    """Convert a camel case string to snake case.

    Args:
        camel_case_string: The string to convert.
    Returns:
        The converted string.
    """
    snake_case_string = camel_case_string[0].lower()
    for char in camel_case_string[1:]:
        if char.isupper():
            snake_case_string += "_" + char.lower()
        else:
            snake_case_string += char
    return snake_case_string


def _get_event_name(event: Event) -> str:
    """Get the name of the event.

    Args:
        event: The event to get the name of.
    Returns:
        The name of the event.
    """
    return _camel_to_snake(event.__class__.__name__)


def issue_event(event: Event) -> None:
    """Transmit an event to Promtail.

    Args:
        event: The metric event to log.
    Raises:
        requests.RequestException: If the HTTP request to Promtail fails.
    """
    event_dict = event.dict()
    event_name = _get_event_name(event)
    event_dict["event"] = event_name

    with METRICS_LOG_PATH.open(mode="a", encoding="utf-8") as metrics_file:
        metrics_file.write(f"{json.dumps(event_dict)}\n")
