# Copyright 2021 Canonical
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
    interval: float
    jitter: float
    timeout: float
    unit: str


class EventTimer:
    """Manages the timer to emit juju event at regular intervals.

    Attributes:
        unit_name (str): Name of the juju unit to emit events to.
    """

    _systemd_path = Path("/etc/systemd/system")

    def __init__(self, unit_name: str):
        """Construct the timer manager.

        Args:
            unit_name (str): Name of the juju unit to emit events to.
        """
        self.unit_name = unit_name
        self._jinja = Environment(loader=FileSystemLoader("templates"), autoescape=True)

    def _render_event_template(self, template_type: str, event_name: str, context: EventConfig):
        template = self._jinja.get_template(f"dispatch-event.{template_type}.j2")
        dest = self._systemd_path / f"ghro.{event_name}.{template_type}"
        dest.write_text(template.render(context))

    def ensure_event_timer(
        self, event_name: str, interval: float, timeout: Optional[float] = None
    ):
        """Ensure that a systemd service and timer are registered to dispatch the given event.

        The interval is how frequently, in minutes, that the event should be dispatched.

        The timeout is the number of seconds before an event is timed out. If not given or 0,
        it defaults to half the interval period.

        Args:
            event_name (str): Name of the juju event to schedule.
            interval (float): Number of minutes between emitting each event.
        """
        # TODO: Split the configuration for service and timer.
        context: EventConfig = {
            "event": event_name,
            "interval": interval,
            "jitter": interval / 4,
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
        except Exception as ex:
            raise TimerEnableError from ex

    def disable_event_timer(self, event_name: str):
        """Disable the systemd timer for the given event.

        Args:
            event_name (str): Name of the juju event to disable.
        """
        try:
            # Don't check for errors in case the timer wasn't registered.
            # Binding for systemctl do no exist, so `subprocess.run` used.
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "stop", f"ghro.{event_name}.timer"], check=False
            )
            subprocess.run(  # nosec B603
                ["/usr/bin/systemctl", "disable", f"ghro.{event_name}.timer"], check=False
            )
        except Exception as ex:
            raise TimerDisableError from ex
