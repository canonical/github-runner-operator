#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

import logging
import subprocess
import urllib.error
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from ops.charm import CharmBase
from ops.framework import EventBase, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from runner import RunnerManager, RunnerError

logger = logging.getLogger(__name__)


class ReconcileRunnersEvent(EventBase):
    """Event representing a periodic check to ensure runners are ok."""


class UpdateRunnerBinEvent(EventBase):
    """Event representing a periodic check for new versions of the runner binary."""


class GithubRunnerOperator(CharmBase):
    _stored = StoredState()
    _systemd_path = Path("/etc/systemd/system")

    def __init__(self, *args):
        super().__init__(*args)

        self._jinja = Environment(loader=FileSystemLoader("templates"))

        self._stored.set_default(
            path=self.config["path"],  # for detecting changes
            runner_bin_url=None,
        )

        self.on.define_event("reconcile_runners", ReconcileRunnersEvent)
        self.on.define_event("update_runner_bin", UpdateRunnerBinEvent)

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reconcile_runners, self._on_reconcile_runners)
        self.framework.observe(self.on.update_runner_bin, self._on_update_runner_bin)
        self.framework.observe(self.on.stop, self._on_stop)

        self.framework.observe(
            self.on.check_runners_action, self._on_check_runners_action
        )
        self.framework.observe(
            self.on.reconcile_runners_action, self._on_reconcile_runners_action
        )
        self.framework.observe(
            self.on.flush_runners_action, self._on_flush_runners_action
        )

    def _get_runner_manager(self, token=None, path=None):
        """Get a RunnerManager instance, or None if missing config."""
        if token is None:
            token = self.config["token"]
        if path is None:
            path = self.config["path"]
        if not (token and path):
            return None
        return RunnerManager(
            path, token, self.app.name, self.config["reconcile-interval"]
        )

    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Installing packages")
        RunnerManager.install_deps()
        runner_manager = self._get_runner_manager()
        if runner_manager:
            self.unit.status = MaintenanceStatus("Installing runner binary")
            try:
                self._stored.runner_bin_url = runner_manager.get_latest_runner_bin_url()
                runner_manager.update_runner_bin(self._stored.runner_bin_url)
            except Exception as e:
                logger.exception("Failed to update runner binary")
                self.unit.status = BlockedStatus(f"Failed to update runner binary: {e}")
                return
            self.unit.status = MaintenanceStatus("Starting runners")
            try:
                self._reconcile_runners(runner_manager)
            except RunnerError as e:
                logger.exception("Failed to start runners")
                self.unit.status = BlockedStatus(f"Failed to start runners: {e}")
            else:
                self.unit.status = ActiveStatus()
        else:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")

    def _on_upgrade_charm(self, event):
        RunnerManager.install_deps()

    def _on_config_changed(self, event):
        self._ensure_event_timer("update-runner-bin", self.config["update-interval"])
        self._ensure_event_timer("reconcile-runners", self.config["reconcile-interval"])

        if self.config["path"] != self._stored.path:
            prev_runner_manager = self._get_runner_manager(path=self._stored.path)
            if prev_runner_manager:
                self.unit.status = MaintenanceStatus(
                    "Removing runners from old org/repo"
                )
                prev_runner_manager.clear()
            self._stored.path = self.config["path"]

        runner_manager = self._get_runner_manager()
        if runner_manager:
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")

    def _on_update_runner_bin(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            return
        old_status = self.unit.status
        try:
            self.unit.status = MaintenanceStatus("Checking for runner updates")
            runner_bin_url = runner_manager.get_latest_runner_bin_url()
        except urllib.error.URLError as e:
            logger.exception("Failed to check for runner updates")
            self.unit.status = BlockedStatus(f"Failed to check for runner updates: {e}")
            return
        if runner_bin_url != self._stored.runner_bin_url:
            self.unit.status = MaintenanceStatus("Updating runner binary")
            try:
                runner_manager.update_runner_bin(runner_bin_url)
            except Exception as e:
                logger.exception("Failed to update runner binary")
                self.unit.status = BlockedStatus(f"Failed to update runner binary: {e}")
                return
            self._stored.runner_bin_url = runner_bin_url
            # TODO: Flush existing runners? What if they're processing a job?
        self.unit.status = old_status

    def _on_reconcile_runners(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager or not runner_manager.runner_bin_path.exists():
            return
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            self._reconcile_runners(runner_manager)
        except Exception as e:
            logger.exception("Failed to reconcile runners")
            self.unit.status = BlockedStatus(f"Failed to reconcile runners: {e}")
        else:
            self.unit.status = ActiveStatus()

    def _on_check_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return
        if not runner_manager.runner_bin_path.exists():
            event.fail("Missing runner binary")
            return

        online = 0
        offline = 0
        unknown = 0
        runner_names = []

        try:
            runner_info = runner_manager.get_info()
        except Exception as e:
            logger.exception("Failed to get runner info")
            event.fail(f"Failed to get runner info: {e}")
            return

        for runner in runner_info:
            if runner.is_online:
                online += 1
                runner_names.append(runner.name)
            elif runner.is_offline:
                offline += 1
            else:
                # might happen if runner dies and GH doesn't notice immediately
                unknown += 1
        event.set_results(
            {
                "online": online,
                "offline": offline,
                "unknown": unknown,
                "runners": ", ".join(runner_names),
            }
        )

    def _on_reconcile_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        try:
            delta = self._reconcile_runners(runner_manager)
        except Exception as e:
            logger.exception("Failed to reconcile runners")
            event.fail(f"Failed to reconcile runners: {e}")
            return
        self._on_check_runners_action(event)
        event.set_results(delta)

    def _on_flush_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        try:
            runner_manager.clear()
            delta = self._reconcile_runners(runner_manager)
        except Exception as e:
            logger.exception("Failed to flush runners")
            event.fail(f"Failed to flush runners: {e}")
            return
        self._on_check_runners_action(event)
        event.set_results(delta)

    def _on_stop(self, event):
        self._disable_event_timer("update-runner-bin")
        self._disable_event_timer("reconcile-runners")
        runner_manager = self._get_runner_manager()
        if runner_manager:
            try:
                runner_manager.clear()
            except Exception:
                # Log but ignore error since we're stopping anyway.
                logger.exception("Failed to clear runners")

    def _reconcile_runners(self, runner_manager):
        # handle deprecated config for `quantity` and `virt-type`

        containers = self.config["containers"]
        if containers == 0 and self.config["virt-type"] == "container":
            containers = self.config["quantity"]

        virtual_machines = self.config["virtual-machines"]
        if virtual_machines == 0 and self.config["virt-type"] == "virtual-machine":
            virtual_machines = self.config["quantity"]

        delta_containers = runner_manager.reconcile("container", containers)
        delta_virtual_machines = runner_manager.reconcile(
            "virtual-machine", virtual_machines
        )
        return {
            "delta": {
                "containers": delta_containers,
                "virtual-machines": delta_virtual_machines,
            }
        }

    def _render_event_tmpl(self, tmpl_type, event_name, context):
        tmpl = self._jinja.get_template(f"dispatch-event.{tmpl_type}.j2")
        dest = self._systemd_path / f"ghro.{event_name}.{tmpl_type}"
        dest.write_text(tmpl.render(context))

    def _ensure_event_timer(self, event_name, interval, timeout=None):
        """Ensure systemd service and timer are registered to dispatch the given event.

        The interval is how frequently, in minutes, that the event should be
        dispatched.

        The timeout is the number of seconds before an event is timed out. If not given
        or 0, it defaults to half the interval period.
        """
        context = {
            "event": event_name,
            "interval": interval,
            "jitter": interval / 4,
            "timeout": timeout or (interval * 60 / 2),
            "unit": self.unit.name,
        }
        self._render_event_tmpl("service", event_name, context)
        self._render_event_tmpl("timer", event_name, context)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", f"ghro.{event_name}.timer"], check=True)
        subprocess.run(["systemctl", "start", f"ghro.{event_name}.timer"], check=True)

    def _disable_event_timer(self, event_name):
        """Disable the systemd timer for the given event."""
        # Don't check for errors in case the timer wasn't registered.
        subprocess.run(["systemctl", "stop", f"ghro.{event_name}.timer"], check=False)
        subprocess.run(
            ["systemctl", "disable", f"ghro.{event_name}.timer"], check=False
        )


if __name__ == "__main__":
    main(GithubRunnerOperator)
