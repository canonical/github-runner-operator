#!/usr/bin/env python3

# Copyright 2022 Canonical
# See LICENSE file for licensing details.

"""Charm for creating and managing GitHub self-hosted runner instances."""

import logging
import urllib.error
from typing import TYPE_CHECKING, Dict, Optional

from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    StopEvent,
    UpgradeCharmEvent,
)
from ops.framework import EventBase, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from event_timer import EventTimer, TimerDisableError, TimerEnableError
from runner import RunnerError, RunnerManager, VMResources

if TYPE_CHECKING:
    from ops.model import JsonObject

logger = logging.getLogger(__name__)


class ReconcileRunnersEvent(EventBase):
    """Event representing a periodic check to ensure runners are ok."""


class UpdateRunnerBinEvent(EventBase):
    """Event representing a periodic check for new versions of the runner binary."""


class GithubRunnerOperator(CharmBase):
    """Charm for managing GitHub self-hosted runners.

    TODO:
    * Remove support of LXD containers, due to security concerns.
    * Review the action results fields, and use TypedDict for the action results, and JSON-like
        return values.
    """

    _stored = StoredState()

    def __init__(self, *args) -> None:
        """Construct the charm."""
        super().__init__(*args)

        self._event_timer = EventTimer(self.unit.name)

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

        self.framework.observe(self.on.check_runners_action, self._on_check_runners_action)
        self.framework.observe(self.on.reconcile_runners_action, self._on_reconcile_runners_action)
        self.framework.observe(self.on.flush_runners_action, self._on_flush_runners_action)

    def _get_runner_manager(
        self, token: Optional[str] = None, path: Optional[str] = None
    ) -> Optional[RunnerManager]:
        """Get a RunnerManager instance, or None if missing config.

        Args:
            token: GitHub personal access token to manager the runners with. Defaults to None.
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name. Defaults to None.

        Returns:
            A instance of RunnerManager if the token and path configuration can be found.
        """
        if token is None:
            token = self.config["token"]
        if path is None:
            path = self.config["path"]
        if not token or not path:
            return None
        return RunnerManager(path, token, self.app.name, self.config["reconcile-interval"])

    def _on_install(self, event: InstallEvent) -> None:
        """Handle the installation of charm.

        Args:
            event: Event of installing charm.
        """
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

    def _on_upgrade_charm(self, event: UpgradeCharmEvent) -> None:
        """Handle the update of charm.

        Args:
            event: Event of charm upgrade.
        """
        RunnerManager.install_deps()

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Handle the configuration change.

        Args:
            event: Event of configuration change.
        """
        try:
            self._event_timer.ensure_event_timer(
                "update-runner-bin", self.config["update-interval"]
            )
            self._event_timer.ensure_event_timer(
                "reconcile-runners", self.config["reconcile-interval"]
            )
        except TimerEnableError as ex:
            logger.exception("Failed to start the event timer")
            self.unit.status = BlockedStatus(
                f"Failed to start timer for regular reconciliation and binary update checks: {ex}"
            )

        if self.config["path"] != self._stored.path:
            prev_runner_manager = self._get_runner_manager(
                path=str(self._stored.path)
            )  # Casting for mypy checks.
            if prev_runner_manager:
                self.unit.status = MaintenanceStatus("Removing runners from old org/repo")
                prev_runner_manager.clear()
            self._stored.path = self.config["path"]

        runner_manager = self._get_runner_manager()
        if runner_manager:
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")

    def _on_update_runner_bin(self, event: UpdateRunnerBinEvent) -> None:
        """Handle checking update of runner binary event.

        Args:
            event: Event of checking update of runner binary.
        """
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

    def _on_reconcile_runners(self, event: ReconcileRunnersEvent) -> None:
        """Handle the reconciliation of runners.

        Args:
            event: Event of reconciling the runner state.
        """
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

    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state.

        Args:
            event: Action event of checking runner states.
        """
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

    def _on_reconcile_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of reconcile of runner state.

        Args:
            event: Action event of reconciling the runner.
        """
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

    def _on_flush_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of flushing all runner and reconciling afterwards.

        Args:
            event: Action event of flushing all runners.
        """
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

    def _on_stop(self, _: StopEvent) -> None:
        """Handle the stopping of the charm.

        Args:
            event: Event of stopping the charm.
        """
        try:
            self._event_timer.disable_event_timer("update-runner-bin")
            self._event_timer.disable_event_timer("reconcile-runners")
        except TimerDisableError as ex:
            logger.exception("Failed to stop the timer")
            self.unit.status = BlockedStatus(f"Failed to stop charm event timer: {ex}")

        runner_manager = self._get_runner_manager()
        if runner_manager:
            try:
                runner_manager.clear()
            except Exception:
                # Log but ignore error since we're stopping anyway.
                logger.exception("Failed to clear runners")

    def _reconcile_runners(self, runner_manager: RunnerManager) -> Dict[str, "JsonObject"]:
        """Reconcile the current runners state and intended runner state.

        Args:
            runner_manager: For querying and managing the runner state.

        Returns:
            Changes in runner number due to reconciling runners.
        """
        virtual_machines_resources = VMResources(
            self.config["vm-cpu"], self.config["vm-memory"], self.config["vm-disk"]
        )
        # handle deprecated config for `quantity` and `virt-type`

        containers = self.config["containers"]
        if containers == 0 and self.config["virt-type"] == "container":
            containers = self.config["quantity"]

        virtual_machines = self.config["virtual-machines"]
        if virtual_machines == 0 and self.config["virt-type"] == "virtual-machine":
            virtual_machines = self.config["quantity"]

        delta_containers = runner_manager.reconcile("container", containers)
        delta_virtual_machines = runner_manager.reconcile(
            "virtual-machine", virtual_machines, virtual_machines_resources
        )
        return {
            "delta": {
                "containers": delta_containers,
                "virtual-machines": delta_virtual_machines,
            }
        }


if __name__ == "__main__":
    main(GithubRunnerOperator)
