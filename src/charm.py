#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for creating and managing GitHub self-hosted runner instances."""

import functools
import logging
import os
import secrets
import shutil
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional, TypeVar

import jinja2
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

from errors import MissingConfigurationError, RunnerError, SubprocessError
from event_timer import EventTimer, TimerDisableError, TimerEnableError
from github_type import GitHubRunnerStatus
from runner_manager import RunnerManager, RunnerManagerConfig
from runner_type import GitHubOrg, GitHubRepo, ProxySetting, VirtualMachineResources
from utilities import execute_command, get_env_var, retry, secure_run_subprocess

if TYPE_CHECKING:
    from ops.model import JsonObject  # pragma: no cover

logger = logging.getLogger(__name__)


class ReconcileRunnersEvent(EventBase):
    """Event representing a periodic check to ensure runners are ok."""


class UpdateRunnerBinEvent(EventBase):
    """Event representing a periodic check for new versions of the runner binary."""


CharmT = TypeVar("CharmT")
EventT = TypeVar("EventT")


def catch_charm_errors(func: Callable[[CharmT, EventT], None]) -> Callable[[CharmT, EventT], None]:
    """Catch unexpected errors in charm.

    This decorator is for unrecoverable errors and sets the charm to
    `BlockedStatus`.

    Args:
        func: Charm function to be decorated.

    Returns:
        Decorated charm function with catching unexpected errors.
    """

    @functools.wraps(func)
    def func_with_catch_unexpected_errors(self, event: EventT) -> None:
        # Safe guard against unexpected error.
        try:
            func(self, event)
        except MissingConfigurationError as err:
            logger.exception("Missing required charm configuration")
            self.unit.status = BlockedStatus(
                f"Missing required charm configuration: {err.configs}"
            )

    return func_with_catch_unexpected_errors


def catch_action_errors(
    func: Callable[[CharmT, ActionEvent], None]
) -> Callable[[CharmT, ActionEvent], None]:
    """Catch unexpected errors in actions.

    Args:
        func: Action function to be decorated.

    Returns:
        Decorated charm function with catching unexpected errors.
    """

    @functools.wraps(func)
    def func_with_catch_errors(self, event: ActionEvent) -> None:
        # Safe guard against unexpected error.
        try:
            func(self, event)
        except MissingConfigurationError as err:
            logger.exception("Missing required charm configuration")
            event.fail(f"Missing required charm configuration: {err.configs}")

    return func_with_catch_errors


class GithubRunnerCharm(CharmBase):
    """Charm for managing GitHub self-hosted runners."""

    _stored = StoredState()

    service_token_path = Path("service_token")
    repo_check_web_service_path = Path("/home/ubuntu/repo_policy_compliance_service")
    repo_check_web_service_script = Path("src/repo_policy_compliance_service.py")
    repo_check_systemd_service = Path("/etc/systemd/system/repo-policy-compliance.service")
    lvm_vg_name = "ramdisk_pool"

    def __init__(self, *args, **kargs) -> None:
        """Construct the charm.

        Args:
            args: List of arguments to be passed to the `CharmBase` class.
            kargs: List of keyword arguments to be passed to the `CharmBase`
                class.
        """
        super().__init__(*args, **kargs)

        self._event_timer = EventTimer(self.unit.name)

        self._stored.set_default(
            path=self.config["path"],  # for detecting changes
            runner_bin_url=None,
        )

        self.proxies: ProxySetting = {}
        if http_proxy := get_env_var("JUJU_CHARM_HTTP_PROXY"):
            self.proxies["http"] = http_proxy
        if https_proxy := get_env_var("JUJU_CHARM_HTTPS_PROXY"):
            self.proxies["https"] = https_proxy
        if no_proxy := get_env_var("JUJU_CHARM_NO_PROXY"):
            self.proxies["no_proxy"] = no_proxy

        self.service_token = None

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
        self.framework.observe(self.on.update_runner_bin_action, self._on_update_runner_bin)

    def _ensure_ramdisk_volume_group(self) -> None:
        """Ensure ramdisk LVM volume group exists."""
        # Check if ramdisk at /dev/ram0 exists.
        result = secure_run_subprocess(["test", "-e", "/dev/ram0"])
        if result.returncode != 0:
            # The block ram disk is set to 1 TiB size, as a way to not limit it.
            # Block ram disk does not pre-allocate the memory.
            # Each LXD instance memory usage is restricted through the LXD profile.
            execute_command(["modprobe", "brd", "rd_size=1073741824", "rd_nr=1"])

        # Check if volume group exits.
        result = secure_run_subprocess(["vgdisplay", self.lvm_vg_name])
        if result.returncode != 0:
            execute_command(["vgcreate", self.lvm_vg_name, "/dev/ram0"])

    def _get_runner_manager(
        self, token: Optional[str] = None, path: Optional[str] = None
    ) -> RunnerManager:
        """Get a RunnerManager instance, or None if missing config.

        Args:
            token: GitHub personal access token to manager the runners with.
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name.

        Returns:
            A instance of RunnerManager.
        """
        if token is None:
            token = self.config["token"]
        if path is None:
            path = self.config["path"]

        missing_configs = []
        if not token:
            missing_configs.append("token")
        if not path:
            missing_configs.append("path")
        if missing_configs:
            raise MissingConfigurationError(missing_configs)

        self._ensure_ramdisk_volume_group()

        if self.service_token is None:
            self.service_token = self._get_service_token()

        if "/" in path:
            paths = path.split("/")
            if len(paths) != 2:
                logger.error("Invalid path %s", path)
                return None

            owner, repo = paths
            path = GitHubRepo(owner=owner, repo=repo)
        else:
            path = GitHubOrg(org=path, group=self.config["group"])

        app_name, unit = self.unit.name.rsplit("/", 1)
        return RunnerManager(
            app_name,
            unit,
            RunnerManagerConfig(path, token, "jammy", self.service_token, self.lvm_vg_name),
            proxies=self.proxies,
        )

    @catch_charm_errors
    def _on_install(self, _event: InstallEvent) -> None:
        """Handle the installation of charm.

        Args:
            event: Event of installing charm.
        """
        self.unit.status = MaintenanceStatus("Installing packages")

        try:
            # The `_start_services`, `_install_deps` includes retry.
            self._install_deps()
            self._start_services()
        except SubprocessError as err:
            logger.exception(err)
            # The charm cannot proceed without dependencies.
            self.unit.status = BlockedStatus("Failed to install dependencies")
            return

        runner_manager = self._get_runner_manager()
        if runner_manager:
            self.unit.status = MaintenanceStatus("Downloading runner binary")
            try:
                runner_info = runner_manager.get_latest_runner_bin_url()
                logger.info(
                    "Downloading %s from: %s", runner_info.filename, runner_info.download_url
                )
                self._stored.runner_bin_url = runner_info.download_url
                runner_manager.update_runner_bin(runner_info)
            # Safe guard against transient unexpected error.
            except Exception as err:  # pylint: disable=broad-exception-caught
                logger.exception("Failed to update runner binary")
                # Failure to download runner binary is a transient error.
                # The charm automatically update runner binary on a schedule.
                self.unit.status = MaintenanceStatus(f"Failed to update runner binary: {err}")
                return
            self.unit.status = MaintenanceStatus("Starting runners")
            try:
                self._reconcile_runners(runner_manager)
                self.unit.status = ActiveStatus()
            except RunnerError as err:
                logger.exception("Failed to start runners")
                self.unit.status = MaintenanceStatus(f"Failed to start runners: {err}")
        else:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")

    @catch_charm_errors
    def _on_upgrade_charm(self, _event: UpgradeCharmEvent) -> None:
        """Handle the update of charm.

        Args:
            event: Event of charm upgrade.
        """
        logger.info("Reinstalling dependencies...")
        self._install_deps()
        self._start_services()

        logger.info("Flushing the runners...")
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            return

        runner_manager.flush()
        self._reconcile_runners(runner_manager)

    @catch_charm_errors
    def _on_config_changed(self, _event: ConfigChangedEvent) -> None:
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
                prev_runner_manager.flush()
            self._stored.path = self.config["path"]

        runner_manager = self._get_runner_manager()
        if runner_manager:
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")

    @catch_charm_errors
    def _on_update_runner_bin(self, _event: UpdateRunnerBinEvent) -> None:
        """Handle checking update of runner binary event.

        Args:
            event: Event of checking update of runner binary.
        """
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            return
        try:
            self.unit.status = MaintenanceStatus("Checking for runner updates")
            runner_info = runner_manager.get_latest_runner_bin_url()
        except urllib.error.URLError as err:
            logger.exception("Failed to check for runner updates")
            # Failure to download runner binary is a transient error.
            # The charm automatically update runner binary on a schedule.
            self.unit.status = MaintenanceStatus(f"Failed to check for runner updates: {err}")
            return

        if runner_info.download_url != self._stored.runner_bin_url:
            self.unit.status = MaintenanceStatus("Updating runner binary")
            try:
                runner_manager.update_runner_bin(runner_info)
            # Safe guard against transient unexpected error.
            except Exception as err:  # pylint: disable=broad-exception-caught
                logger.exception("Failed to update runner binary")
                # Failure to download runner binary is a transient error.
                # The charm automatically update runner binary on a schedule.
                self.unit.status = MaintenanceStatus(f"Failed to update runner binary: {err}")
                return
            self._stored.runner_bin_url = runner_info.download_url

            # Flush the non-busy runner and reconcile.
            runner_manager.flush(flush_busy=False)
            self._reconcile_runners(runner_manager)

        self.unit.status = ActiveStatus()

    @catch_charm_errors
    def _on_reconcile_runners(self, _event: ReconcileRunnersEvent) -> None:
        """Handle the reconciliation of runners.

        Args:
            event: Event of reconciling the runner state.
        """
        if not RunnerManager.runner_bin_path.is_file():
            logger.warning("Unable to reconcile due to missing runner binary")
            return

        runner_manager = self._get_runner_manager()
        if not runner_manager:
            self.unit.status = BlockedStatus("Missing token or org/repo path config")
            return
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            self._reconcile_runners(runner_manager)
        # Safe guard against transient unexpected error.
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to reconcile runners")
            self.unit.status = MaintenanceStatus(f"Failed to reconcile runners: {err}")
            return

        self.unit.status = ActiveStatus()

    @catch_action_errors
    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state.

        Args:
            event: Action event of checking runner states.
        """
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return
        if runner_manager.runner_bin_path is None:
            event.fail("Missing runner binary")
            return

        online = 0
        offline = 0
        unknown = 0
        runner_names = []

        runner_info = runner_manager.get_github_info()

        for runner in runner_info:
            if runner.status == GitHubRunnerStatus.ONLINE.value:
                online += 1
                runner_names.append(runner.name)
            elif runner.status == GitHubRunnerStatus.OFFLINE.value:
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

    @catch_action_errors
    def _on_reconcile_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of reconcile of runner state.

        Args:
            event: Action event of reconciling the runner.
        """
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        delta = self._reconcile_runners(runner_manager)

        self._on_check_runners_action(event)
        event.set_results(delta)

    @catch_action_errors
    def _on_flush_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of flushing all runner and reconciling afterwards.

        Args:
            event: Action event of flushing all runners.
        """
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            event.fail("Missing token or org/repo path config")
            return

        runner_manager.flush()
        delta = self._reconcile_runners(runner_manager)

        self._on_check_runners_action(event)
        event.set_results(delta)

    @catch_charm_errors
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
                runner_manager.flush()
            # Safe guard against unexpected error.
            except Exception:  # pylint: disable=broad-exception-caught
                # Log but ignore error since we're stopping anyway.
                logger.exception("Failed to clear runners")

    def _reconcile_runners(self, runner_manager: RunnerManager) -> Dict[str, "JsonObject"]:
        """Reconcile the current runners state and intended runner state.

        Args:
            runner_manager: For querying and managing the runner state.

        Returns:
            Changes in runner number due to reconciling runners.
        """
        virtual_machines_resources = VirtualMachineResources(
            self.config["vm-cpu"], self.config["vm-memory"], self.config["vm-disk"]
        )

        virtual_machines = self.config["virtual-machines"]

        try:
            delta_virtual_machines = runner_manager.reconcile(
                virtual_machines, virtual_machines_resources
            )
            return {"delta": {"virtual-machines": delta_virtual_machines}}
        # Safe guard against transient unexpected error.
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to reconcile runners.")
            # Failure to reconcile runners is a transient error.
            # The charm automatically reconciles runners on a schedule.
            self.unit.status = MaintenanceStatus(f"Failed to reconcile runners: {err}")
            return {"delta": {"virtual-machines": 0}}

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5)
    def _install_deps(self) -> None:
        """Install dependencies."""
        logger.info("Installing charm dependencies.")

        # Binding for snap, apt, and lxd init commands are not available so subprocess.run used.
        env = {}
        if "http" in self.proxies:
            env["HTTP_PROXY"] = self.proxies["http"]
            env["http_proxy"] = self.proxies["http"]
        if "https" in self.proxies:
            env["HTTPS_PROXY"] = self.proxies["https"]
            env["https_proxy"] = self.proxies["https"]
        if "no_proxy" in self.proxies:
            env["NO_PROXY"] = self.proxies["no_proxy"]
            env["no_proxy"] = self.proxies["no_proxy"]

        execute_command(["/usr/bin/apt-get", "install", "-qy", "gunicorn", "python3-pip"])
        execute_command(
            [
                "/usr/bin/pip",
                "install",
                "git+https://github.com/canonical/repo-policy-compliance@main",
            ],
            env=env,
        )

        execute_command(
            ["/usr/bin/apt-get", "remove", "-qy", "lxd", "lxd-client"], check_exit=False
        )
        execute_command(
            [
                "/usr/bin/apt-get",
                "install",
                "-qy",
                "cpu-checker",
                "libvirt-clients",
                "libvirt-daemon-driver-qemu",
                "apparmor-utils",
            ],
        )
        execute_command(["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"])
        execute_command(["/usr/bin/snap", "refresh", "lxd", "--channel=latest/stable"])
        execute_command(["/snap/bin/lxd", "waitready"])
        execute_command(["/snap/bin/lxd", "init", "--auto"])
        execute_command(["/usr/bin/chmod", "a+wr", "/var/snap/lxd/common/lxd/unix.socket"])
        execute_command(["/snap/bin/lxc", "network", "set", "lxdbr0", "ipv6.address", "none"])
        logger.info("Finished installing charm dependencies.")

        logger.info("Setting apparmor to complain mode.")
        self._apparmor_complain_mode(
            [
                "/etc/apparmor.d/lsb_release",
                "/etc/apparmor.d/nvidia_modprobe",
                "/etc/apparmor.d/sbin.dhclient",
                "/etc/apparmor.d/usr.bin.man",
                "/etc/apparmor.d/usr.bin.tcpdump",
                "/etc/apparmor.d/usr.lib.snapd.snap-confine.real",
                "/etc/apparmor.d/usr.sbin.rsyslogd",
            ]
        )

    def _apparmor_complain_mode(self, profiles: list[str]) -> None:
        """Enable complain mode for the apparmor profile.

        Args:
            profiles: Profiles to enable complain mode.
        """
        for profile in profiles:
            execute_command(["aa-complain", profile])

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5)
    def _start_services(self) -> None:
        """Start services."""
        logger.info("Starting charm services...")

        if self.service_token is None:
            self.service_token = self._get_service_token()

        # Move script to home directory
        logger.info("Loading the repo policy compliance flask app...")
        os.makedirs(self.repo_check_web_service_path, exist_ok=True)
        shutil.copyfile(
            self.repo_check_web_service_script,
            self.repo_check_web_service_path / "app.py",
        )

        # Move the systemd service.
        logger.info("Loading the repo policy compliance gunicorn systemd service...")
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True
        )

        service_content = environment.get_template("repo-policy-compliance.service.j2").render(
            working_directory=str(self.repo_check_web_service_path),
            charm_token=self.service_token,
            github_token=self.config["token"],
            proxies=self.proxies,
        )
        self.repo_check_systemd_service.write_text(service_content, encoding="utf-8")

        execute_command(["/usr/bin/systemctl", "start", "repo-policy-compliance"])
        execute_command(["/usr/bin/systemctl", "enable", "repo-policy-compliance"])

        logger.info("Finished starting charm services")

    def _get_service_token(self) -> str:
        """Get the service token.

        Returns:
            The service token.
        """
        logger.info("Getting the secret token...")
        if self.service_token_path.exists():
            logger.info("Found existing token file.")
            service_token = self.service_token_path.read_text(encoding="utf-8")
        else:
            logger.info("Generate new token.")
            service_token = secrets.token_hex(16)
            self.service_token_path.write_text(service_token, encoding="utf-8")

        return service_token


if __name__ == "__main__":
    main(GithubRunnerCharm)
