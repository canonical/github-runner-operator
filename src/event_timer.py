# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""EventTimer for scheduling dispatch of juju event on regular intervals."""
import logging
import subprocess  # nosec B404
from pathlib import Path
from typing import Optional, TypedDict

import jinja2

from utilities import execute_command
from utilities import logger as utilities_logger

BIN_SYSTEMCTL = "/usr/bin/systemctl"

logger = logging.getLogger(__name__)


class TimerError(Exception):
    """Generic timer error as base exception."""


class TimerEnableError(TimerError):
    """Raised when unable to enable a event timer."""


class TimerDisableError(TimerError):
    """Raised when unable to disable a event timer."""


class TimerStatusError(TimerError):
    """Raised when unable to check status of a event timer."""


class EventConfig(TypedDict):
    """Configuration used by service and timer templates."""

    event: str
    interval: int
    random_delay: int
    timeout: int
    unit: str


class EventTimer:
    """Manages the timer to emit juju events at regular intervals.

    Attributes:
        unit_name (str): Name of the juju unit to emit events to.
    """

    _systemd_path = Path("/etc/systemd/system")

    def __init__(self, unit_name: str):
        """Construct the timer manager.

        Args:
            unit_name: Name of the juju unit to emit events to.
        """
        self.unit_name = unit_name
        self._jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True
        )

    def _render_event_template(self, template_type: str, event_name: str, context: EventConfig):
        """Write event configuration files to systemd path.

        Args:
            template_type: Name of the template type to use. Can be 'service' or 'timer'.
            event_name: Name of the event to schedule.
            context: Addition configuration for the event to schedule.
        """
        template = self._jinja.get_template(f"dispatch-event.{template_type}.j2")
        dest = self._systemd_path / f"ghro.{event_name}.{template_type}"
        dest.write_text(template.render(context))

    def is_active(self, event_name: str) -> bool:
        """Check if the systemd timer is active for the given event.

        Args:
            event_name: Name of the juju event to check.

        Returns:
            True if the timer is enabled, False otherwise.

        Raises:
            TimerStatusError: Timer status cannot be determined.
        """
        try:
            _, ret_code = execute_command(
                [BIN_SYSTEMCTL, "is-active", f"ghro.{event_name}.timer"], check_exit=False
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
            raise TimerStatusError from ex

        if ret_code == 0:
            return True

        if utilities_logger.isEnabledFor(logging.DEBUG):
            try:
                execute_command([BIN_SYSTEMCTL, "list-timers", "--all"], check_exit=False)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
                logger.exception("Unable to list systemd timers: %s", ex)
        return False

    def ensure_event_timer(self, event_name: str, interval: int, timeout: Optional[int] = None):
        """Ensure that a systemd service and timer are registered to dispatch the given event.

        The interval is how frequently, in minutes, the event should be dispatched.

        The timeout is the number of seconds before an event is timed out. If not set or 0,
        it defaults to half the interval period.

        Args:
            event_name: Name of the juju event to schedule.
            interval: Number of minutes between emitting each event.
            timeout: Timeout for each event handle in minutes.

        Raises:
            TimerEnableError: Timer cannot be started. Events will be not emitted.
        """
        if timeout is not None:
            timeout_in_secs = timeout * 60
        else:
            timeout_in_secs = interval * 30

        context: EventConfig = {
            "event": event_name,
            "interval": interval,
            "random_delay": interval // 4,
            "timeout": timeout_in_secs,
            "unit": self.unit_name,
        }
        self._render_event_template("service", event_name, context)
        self._render_event_template("timer", event_name, context)

        systemd_timer = f"ghro.{event_name}.timer"
        try:
            execute_command([BIN_SYSTEMCTL, "daemon-reload"])
            execute_command([BIN_SYSTEMCTL, "enable", systemd_timer])
            execute_command([BIN_SYSTEMCTL, "start", systemd_timer])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
            raise TimerEnableError(f"Unable to enable systemd timer {systemd_timer}") from ex

    def disable_event_timer(self, event_name: str):
        """Disable the systemd timer for the given event.

        Args:
            event_name: Name of the juju event to disable.

        Raises:
            TimerDisableError: Timer cannot be stopped. Events will be emitted continuously.
        """
        systemd_timer = f"ghro.{event_name}.timer"
        try:
            # Don't check for errors in case the timer wasn't registered.
            execute_command([BIN_SYSTEMCTL, "stop", systemd_timer], check_exit=False)
            execute_command([BIN_SYSTEMCTL, "disable", systemd_timer], check_exit=False)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
            raise TimerDisableError(f"Unable to disable systemd timer {systemd_timer}") from ex
