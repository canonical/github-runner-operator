#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Models and functions for the metric events."""
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, NonNegativeFloat

from errors import IssueMetricEventError, LogrotateSetupError, SubprocessError
from utilities import execute_command

LOG_ROTATE_TIMER_SYSTEMD_SERVICE = "logrotate.timer"

SYSTEMCTL_PATH = "/usr/bin/systemctl"

LOGROTATE_CONFIG = Path("/etc/logrotate.d/github-runner-metrics")
METRICS_LOG_PATH = Path("/var/log/github-runner-metrics.log")


logger = logging.getLogger(__name__)


class Event(BaseModel):
    """Base class for metric events.

    Attributes:
         timestamp: The UNIX time stamp of the time at which the event was originally issued.
         event: The name of the event. Will be set to the class name in snake case if not provided.
    """

    timestamp: NonNegativeFloat
    event: str

    @staticmethod
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

    def __init__(self, *args, **kwargs):
        """Initialize the event.

        Args:
            *args: The positional arguments to pass to the base class.
            **kwargs: The keyword arguments to pass to the base class. These are used to set the
                specific fields. E.g. timestamp=12345 will set the timestamp field to 12345.
        """
        if "event" not in kwargs:
            event = self._camel_to_snake(self.__class__.__name__)
            kwargs["event"] = event
        super().__init__(*args, **kwargs)


class RunnerInstalled(Event):
    """Metric event for when a runner is installed.

    Attributes:
        flavor: Describes the characteristics of the runner.
          The flavor could be for example "small".
        duration: The duration of the installation in seconds.
    """

    flavor: str
    duration: NonNegativeFloat


class RunnerStart(Event):
    """Metric event for when a runner is started.

    Attributes:
        flavor: Describes the characteristics of the runner.
          The flavor could be for example "small".
        workflow: The workflow name.
        repo: The repository name.
        github_event: The github event.
        idle: The idle time in seconds.
        queue_duration: The time in seconds it took before the runner picked up the job.
          This is optional as we rely on the Github API and there may be problems
          retrieving the data.
    """

    flavor: str
    workflow: str
    repo: str
    github_event: str
    idle: NonNegativeFloat
    queue_duration: Optional[NonNegativeFloat]


class CodeInformation(BaseModel):
    """Information about a status code.

    This could e.g. be an exit code or a http status code.

    Attributes:
        code: The status code.
    """

    code: int


class RunnerStop(Event):
    """Metric event for when a runner is stopped.

    Attributes:
        flavor: Describes the characteristics of the runner.
          The flavor could be for example "small".
        workflow: The workflow name.
        repo: The repository name.
        github_event: The github event.
        status: A string describing the reason for stopping the runner.
        status_info: More information about the status.
        job_duration: The duration of the job in seconds.
    """

    flavor: str
    workflow: str
    repo: str
    github_event: str
    status: str
    status_info: Optional[CodeInformation]
    job_duration: NonNegativeFloat


class Reconciliation(Event):
    """Metric event for when the charm has finished reconciliation.

    Attributes:
        flavor: Describes the characteristics of the runner.
          The flavor could be for example "small".
        crashed_runners: The number of crashed runners.
        idle_runners: The number of idle runners.
        duration: The duration of the reconciliation in seconds.
    """

    flavor: str
    crashed_runners: int
    idle_runners: int
    duration: NonNegativeFloat


def issue_event(event: Event) -> None:
    """Issue a metric event.

    The metric event is logged to the metrics log.

    Args:
        event: The metric event to log.

    Raises:
        IssueMetricEventError: If the event cannot be logged.
    """
    try:
        with METRICS_LOG_PATH.open(mode="a", encoding="utf-8") as metrics_file:
            metrics_file.write(f"{event.json(exclude_none=True)}\n")
    except OSError as exc:
        raise IssueMetricEventError(f"Cannot write to {METRICS_LOG_PATH}") from exc


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
        LogrotateSetupError: If the logrotate.timer cannot be enabled.
    """
    _configure_logrotate()

    try:
        _enable_logrotate()
    except SubprocessError as error:
        raise LogrotateSetupError() from error
