#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Models and functions for the metric events."""
import json
import logging
from pathlib import Path

from pydantic import BaseModel, NonNegativeInt

from utilities import execute_command

LOG_ROTATE_TIMER_SYSTEMD_SERVICE = "logrotate.timer"

SYSTEMCTL_PATH = "/usr/bin/systemctl"

LOGROTATE_CONFIG = Path("/etc/logrotate.d/github-runner-metrics")
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


class RunnerStart(Event):
    """Metric event for when a runner is started.

    Attrs:
        flavor: Describes the characteristics of the runner.
          The flavour could be for example "small".
        workflow: The workflow name.
        repo: The repository name.
        github_event: The github event.
        idle: The idle time in seconds.
    """

    flavor: str
    workflow: str
    repo: str
    github_event: str
    idle: NonNegativeInt


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
    """Issue a metric event.

    The metric event is logged to the metrics log.

    Args:
        event: The metric event to log.
    Raises:
        OSError: If an error occurs while writing the metrics log.
    """
    event_dict = event.dict()
    event_name = _get_event_name(event)
    event_dict["event"] = event_name

    with METRICS_LOG_PATH.open(mode="a", encoding="utf-8") as metrics_file:
        metrics_file.write(f"{json.dumps(event_dict)}\n")


def _enable_logrotate() -> None:
    """Enable and start the logrotate timer if it is not active.

    Raises:
        SubprocessError: If the logrotate.timer cannot be enabled and started.
    """
    execute_command([SYSTEMCTL_PATH, "enable", LOG_ROTATE_TIMER_SYSTEMD_SERVICE], check_exit=True)

    _, retcode = execute_command(
        [SYSTEMCTL_PATH, "is-active", "--quiet", LOG_ROTATE_TIMER_SYSTEMD_SERVICE]
    )
    if retcode != 0:
        execute_command(
            [SYSTEMCTL_PATH, "start", LOG_ROTATE_TIMER_SYSTEMD_SERVICE], check_exit=True
        )


def _configure_logrotate() -> None:
    """Configure logrotate for the metrics log."""
    # Set rotate to 0 to not keep the old metrics log file to avoid sending the
    # metrics to Loki twice, which may happen if there is a corrupt log scrape configuration.
    LOGROTATE_CONFIG.write_text(
        f"""{str(METRICS_LOG_PATH)} {{
    rotate 0
    missingok
    notifempty
    create
}}
""",
        encoding="utf-8",
    )


def setup_logrotate():
    """Configure logrotate for the metrics log.

    Raises:
        SubprocessError: If the logrotate.timer cannot be enabled.
    """
    _enable_logrotate()
    _configure_logrotate()
