# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""EventTimer for scheduling dispatch of juju event on regular intervals."""

import subprocess  # nosec B404
from pathlib import Path
from typing import Optional, TypedDict

from jinja2 import Environment, FileSystemLoader


class TimerEnableError(Exception):
    """Raised when unable to enable a event timer."""


class TimerDisableError(Exception):
    """Raised when unable to disable a event timer."""


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
        self._jinja = Environment(loader=FileSystemLoader("templates"), autoescape=True)

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

    def ensure_event_timer(self, event_name: str, interval: int, timeout: Optional[int] = None):
        """Ensure that a systemd service and timer are registered to dispatch the given event.

        The interval is how frequently, in minutes, the event should be dispatched.

        The timeout is the number of seconds before an event is timed out. If not set or 0,
        it defaults to half the interval period.

        Args:
            event_name: Name of the juju event to schedule.
            interval: Number of minutes between emitting each event.

        Raises:
            TimerEnableError: Timer cannot be started. Events will be not emitted.
        """
        context: EventConfig = {
            "event": event_name,
            "interval": interval,
            "random_delay": interval // 4,
            "timeout": timeout or (interval * 30),
            "unit": self.unit_name,
        }
        self._render_event_template("service", event_name, context)
        self._render_event_template("timer", event_name, context)
        try:
            # Binding for systemctl do no exist, so `subprocess.run` used.
            subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True)  # nosec B603
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "enable", f"ghro.{event_name}.timer"], check=True
            )
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "start", f"ghro.{event_name}.timer"], check=True
            )
        except subprocess.CalledProcessError as ex:
            raise TimerEnableError from ex
        except subprocess.TimeoutExpired as ex:
            raise TimerEnableError from ex

    def disable_event_timer(self, event_name: str):
        """Disable the systemd timer for the given event.

        Args:
            event_name: Name of the juju event to disable.

        Raises:
            TimerDisableError: Timer cannot be stopped. Events will be emitted continuously.
        """
        try:
            # Don't check for errors in case the timer wasn't registered.
            # Binding for systemctl does no exist, so `subprocess.run` used.
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "stop", f"ghro.{event_name}.timer"], check=False
            )
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "disable", f"ghro.{event_name}.timer"], check=False
            )
        except subprocess.CalledProcessError as ex:
            raise TimerEnableError from ex
        except subprocess.TimeoutExpired as ex:
            raise TimerEnableError from ex
