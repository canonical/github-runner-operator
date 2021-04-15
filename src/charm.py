#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

import logging

from crontab import CronTab
from ops.charm import CharmBase
from ops.framework import EventBase, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from runner import Runner

logger = logging.getLogger(__name__)


class CheckRunnersEvent(EventBase):
    """Event to request a runner check"""


class GithubRunnerOperator(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.on.define_event("check_runners", CheckRunnersEvent)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(
            self.on.check_runners_action, self._on_check_runners_action
        )
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.check_runners, self._on_check_runners)
        self._stored.set_default(path="")
        self._runner = Runner(self.config["path"], self.config["token"])
        self._cron_tab = CronTab

    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Installing packages")
        self._runner.install()

    def _on_config_changed(self, event):
        if self._stored.path:
            if self._stored.path != self.config["path"]:
                logger.error("Changing path not supported")
                self.unit.status = BlockedStatus("Path can not be changed")
                return
        else:
            if self.config["path"]:
                self._stored.path = self.config["path"]

        if not (self.config["token"] and self._stored.path):
            self.unit.status = BlockedStatus("Waiting for Token and Path config")
            return

        self._reconcile_runners()
        self._add_cron("check-runners", self.config["check-interval"])

    def _on_check_runners(self, event):
        if not (self.config["token"] and self._stored.path):
            logger.info("Not checking runners, missing config")
            return
        self._reconcile_runners()

    def _on_check_runners_action(self, event):
        if not (self.config["token"] and self._stored.path):
            event.set_results({"status": "Check aborted, config options missing"})
            return

        self._reconcile_runners()
        event.set_results({"status": "Completed runner check"})

    def _reconcile_runners(self):
        delta = self.config["quantity"] - self._runner.active_count()
        logger.info(f"Reconciling {delta} runners")
        self._runner.remove_runners()
        while delta > 0:
            self.unit.status = MaintenanceStatus(f"Installing {delta} runner(s)")
            try:
                self._runner.create(image="ubuntu", virt=self.config["virt-type"])
            except RuntimeError as e:
                logger.error("Failed to create runner")
                logger.error(f"Error: {e}")
            delta = self.config["quantity"] - self._runner.active_count()
        self.unit.status = ActiveStatus("Active and registered")

    def _on_stop(self, event):
        self._remove_cron("check-runners")
        self._runner.remove_runners()

    def _add_cron(self, event, interval):
        """Add a cron job for the provided event to run at the provided interval."""
        root_cron = self._cron_tab(user="root")
        comment = f"Charm cron for {event}"

        # Remove if it exists and write with the possibly updated interval
        self._remove_cron(event)

        unit = self.unit.name
        dispatch = str(self.charm_dir / "dispatch")
        command = f"juju-run {unit} 'JUJU_DISPATCH_PATH={event} {dispatch}'"
        job = root_cron.new(command=command, comment=comment)
        job.setall(interval)
        root_cron.write()

    def _remove_cron(self, event):
        """Remove cron job for provided event."""
        root_cron = self._cron_tab(user="root")
        try:
            job = next(root_cron.find_comment(f"Charm cron for {event}"))
            root_cron.remove(job)
            root_cron.write()
        except StopIteration:
            pass  # Not found


if __name__ == "__main__":
    main(GithubRunnerOperator)
