#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

import logging

from crontab import CronTab
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

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(
            path=self.config["path"],  # for detecting changes
            runner_bin_url=None,
        )
        self._cron_tab = CronTab

        self.on.define_event("reconcile_runners", ReconcileRunnersEvent)
        self.on.define_event("update_runner_bin", UpdateRunnerBinEvent)

        self.framework.observe(self.on.install, self._on_install)
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
        return RunnerManager(path, token, self.app.name)

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
                runner_manager.reconcile(self.config["quantity"])
            except RunnerError as e:
                logger.exception("Failed to start runners")
                self.unit.status = BlockedStatus(f"Failed to start runners: {e}")
            else:
                self.unit.status = ActiveStatus()

    def _on_config_changed(self, event):
        self._ensure_cron("update-runner-bin", self.config["update-interval"])
        self._ensure_cron("reconcile-runners", self.config["reconcile-interval"])

        if self.config["path"] != self._stored.path:
            prev_runner_manager = self._get_runner_manager(path=self._stored.path)
            if prev_runner_manager:
                self.unit.status = MaintenanceStatus(
                    "Removing runners from old org/repo"
                )
                prev_runner_manager.clear()
            self._stored.path = self.config["path"]

        runner_manager = self._get_runner_manager()
        if not runner_manager:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")
            return

    def _on_update_runner_bin(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            return
        old_status = self.unit.status
        self.unit.status = MaintenanceStatus("Checking for runner updates")
        runner_bin_url = runner_manager.get_latest_runner_bin_url()
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
        if not runner_manager:
            return
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            self.runner_manager.reconcile(self.config["quantity"])
        except RunnerError as e:
            self.unit.status = BlockedStatus(f"Failed to reconcile runners: {e}")
        else:
            self.unit.status = ActiveStatus()

    def _on_check_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        offline = 0
        unregistered = 0
        active = 0
        unknown = 0

        try:
            runner_info = runner_manager.get_info()
        except RunnerError as e:
            event.fail(f"Failed to get runner info: {e}")
            return

        for runner in runner_info:
            if runner.is_active:
                active += 1
            elif runner.is_offline:
                offline += 1
            elif runner.is_unregistered:
                unregistered += 1
            else:
                # might happen if runner dies and GH doesn't notice immediately
                unknown += 1
        event.set_results(
            {
                "offline": offline,
                "unregistered": unregistered,
                "active": active,
                "unknown": unknown,
            }
        )

    def _on_reconcile_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        try:
            delta = runner_manager.reconcile(self.config["quantity"])
        except RunnerError as e:
            event.fail(f"Failed to reconcile runners: {e}")
            return
        self._on_check_runners_action(event)
        event.set_results({"delta": delta})

    def _on_flush_runners_action(self, event):
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        try:
            runner_manager.clear()
            delta = runner_manager.reconcile(self.config["quantity"])
        except RunnerError as e:
            event.fail(f"Failed to flush runners: {e}")
            return
        self._on_check_runners_action(event)
        event.set_results({"delta": delta})

    def _on_stop(self, event):
        self._remove_cron("update-runner-bin")
        self._remove_cron("reconcile-runners")
        runner_manager = self._get_runner_manager()
        if runner_manager:
            runner_manager.clear()

    def _ensure_cron(self, event_name, interval, timeout=...):
        """Add a cron job to dispatch an event.

        Only one cron job can be registered per event; duplicates will replace an existing
        job. The event will be dispatched to the charm code via `juju-run`.

        Currently supported events are: reconcile-runners

        The interval is how frequently, in minutes, that the event should be dispatched.

        The timeout is the number of seconds before an event is timed out. If not given,
        it defaults to half the interval period.
        """
        if timeout is ...:
            timeout = interval * 60 / 2

        # Remove existing entries before adding the new with a possibly updated interval
        self._remove_cron(event_name)

        root_cron = self._cron_tab(user="root")
        comment = f"Charm cron for {event_name}"
        dispatch = self.charm_dir / "scripts" / "dispatch-event.sh"
        command = f"{dispatch} {self.unit.name} {event_name} {timeout}"
        job = root_cron.new(command=command, comment=comment)
        job.setall(f"*/{interval} * * * *")
        root_cron.write()

    def _remove_cron(self, event_name):
        """Remove cron job for provided event."""
        root_cron = self._cron_tab(user="root")
        for job in root_cron.find_comment(f"Charm cron for {event_name}"):
            root_cron.remove(job)
        root_cron.write()


if __name__ == "__main__":
    main(GithubRunnerOperator)
