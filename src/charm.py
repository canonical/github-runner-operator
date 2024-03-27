#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# 2024/03/12 The module contains too many lines which are scheduled for refactoring.
# pylint: disable=too-many-lines

"""Charm for creating and managing GitHub self-hosted runner instances."""

import functools
import logging
import os
import secrets
import shutil
import urllib.error
from pathlib import Path
from typing import Any, Callable, Dict, Sequence, TypeVar

import jinja2
import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    StartEvent,
    StopEvent,
    UpdateStatusEvent,
    UpgradeCharmEvent,
)
from ops.framework import EventBase, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

import metrics
from charm_state import (
    DEBUG_SSH_INTEGRATION_NAME,
    LABELS_CONFIG_NAME,
    CharmConfigInvalidError,
    CharmState,
    GithubPath,
    InstanceType,
    ProxyConfig,
    RunnerStorage,
    VirtualMachineResources,
    parse_github_path,
)
from errors import (
    ConfigurationError,
    LogrotateSetupError,
    MissingRunnerBinaryError,
    OpenStackUnauthorizedError,
    RunnerBinaryError,
    RunnerError,
    SubprocessError,
    TokenError,
)
from event_timer import EventTimer, TimerStatusError
from firewall import Firewall, FirewallEntry
from github_client import GithubClient
from github_type import GitHubRunnerStatus
from openstack_cloud import openstack_manager
from openstack_cloud.openstack_manager import OpenstackRunnerManager
from runner import LXD_PROFILE_YAML
from runner_manager import RunnerManager, RunnerManagerConfig
from runner_manager_type import FlushMode, OpenstackRunnerManagerConfig
from utilities import bytes_with_unit_to_kib, execute_command, retry

RECONCILE_RUNNERS_EVENT = "reconcile-runners"

logger = logging.getLogger(__name__)


class ReconcileRunnersEvent(EventBase):
    """Event representing a periodic check to ensure runners are ok."""


CharmT = TypeVar("CharmT")
EventT = TypeVar("EventT")


def catch_charm_errors(func: Callable[[CharmT, EventT], None]) -> Callable[[CharmT, EventT], None]:
    """Catch common errors in charm.

    Args:
        func: Charm function to be decorated.

    Returns:
        Decorated charm function with catching common errors.
    """

    @functools.wraps(func)
    def func_with_catch_errors(self, event: EventT) -> None:
        try:
            func(self, event)
        except ConfigurationError as err:
            logger.exception("Issue with charm configuration")
            self.unit.status = BlockedStatus(str(err))
        except TokenError as err:
            logger.exception("Issue with GitHub token")
            self.unit.status = BlockedStatus(str(err))
        except MissingRunnerBinaryError:
            logger.exception("Missing runner binary")
            self.unit.status = MaintenanceStatus(
                "GitHub runner application not downloaded; the charm will retry download on "
                "reconcile interval"
            )
        except OpenStackUnauthorizedError:
            logger.exception("Unauthorized OpenStack connection")
            self.unit.status = BlockedStatus(
                "Unauthorized OpenStack connection. Check credentials."
            )

    return func_with_catch_errors


def catch_action_errors(
    func: Callable[[CharmT, ActionEvent], None]
) -> Callable[[CharmT, ActionEvent], None]:
    """Catch common errors in actions.

    Args:
        func: Action function to be decorated.

    Returns:
        Decorated charm function with catching common errors.
    """

    @functools.wraps(func)
    def func_with_catch_errors(self, event: ActionEvent) -> None:
        try:
            func(self, event)
        except ConfigurationError as err:
            logger.exception("Issue with charm configuration")
            self.unit.status = BlockedStatus(str(err))
            event.fail(str(err))
        except MissingRunnerBinaryError:
            logger.exception("Missing runner binary")
            err_msg = (
                "GitHub runner application not downloaded; the charm will retry download on "
                "reconcile interval"
            )
            self.unit.status = MaintenanceStatus(err_msg)
            event.fail(err_msg)

    return func_with_catch_errors


class GithubRunnerCharm(CharmBase):
    """Charm for managing GitHub self-hosted runners."""

    _stored = StoredState()

    service_token_path = Path("service_token")
    repo_check_web_service_path = Path("/home/ubuntu/repo_policy_compliance_service")
    repo_check_web_service_script = Path("scripts/repo_policy_compliance_service.py")
    repo_check_systemd_service = Path("/etc/systemd/system/repo-policy-compliance.service")
    juju_storage_path = Path("/storage/juju")
    ram_pool_path = Path("/storage/ram")
    kernel_module_path = Path("/etc/modules")

    def __init__(self, *args, **kargs) -> None:
        """Construct the charm.

        Args:
            args: List of arguments to be passed to the `CharmBase` class.
            kargs: List of keyword arguments to be passed to the `CharmBase`
                class.
        """
        super().__init__(*args, **kargs)
        self._grafana_agent = COSAgentProvider(self)

        self.service_token: str | None = None
        self._event_timer = EventTimer(self.unit.name)

        if LXD_PROFILE_YAML.exists():
            if self.config.get("test-mode") != "insecure":
                raise RuntimeError("lxd-profile.yaml detected outside test mode")
            logger.critical("test mode is enabled")

        self._stored.set_default(
            path=self.config["path"],  # for detecting changes
            token=self.config["token"],  # for detecting changes
            labels=self.config[LABELS_CONFIG_NAME],  # for detecting changes
            runner_bin_url=None,
        )

        self.on.define_event("reconcile_runners", ReconcileRunnersEvent)

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(
            self.on[DEBUG_SSH_INTEGRATION_NAME].relation_changed,
            self._on_debug_ssh_relation_changed,
        )
        self.framework.observe(self.on.reconcile_runners, self._on_reconcile_runners)
        self.framework.observe(self.on.check_runners_action, self._on_check_runners_action)
        self.framework.observe(self.on.reconcile_runners_action, self._on_reconcile_runners_action)
        self.framework.observe(self.on.flush_runners_action, self._on_flush_runners_action)
        self.framework.observe(
            self.on.update_dependencies_action, self._on_update_dependencies_action
        )
        self.framework.observe(self.on.update_status, self._on_update_status)

    def _setup_state(self) -> CharmState:
        """Set up the charm state."""
        try:
            return CharmState.from_charm(self)
        except CharmConfigInvalidError as exc:
            raise ConfigurationError(exc.msg) from exc

    def _create_memory_storage(self, path: Path, size: int) -> None:
        """Create a tmpfs-based LVM volume group.

        Args:
            path: Path to directory for memory storage.
            size: Size of the tmpfs in kilobytes.

        Raises:
            RunnerError: Unable to setup storage for runner.
        """
        if size <= 0:
            return

        try:
            # Create tmpfs if not exists, else resize it.
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                execute_command(
                    ["mount", "-t", "tmpfs", "-o", f"size={size}k", "tmpfs", str(path)]
                )
            else:
                execute_command(["mount", "-o", f"remount,size={size}k", str(path)])
        except (OSError, SubprocessError) as err:
            logger.exception("Unable to setup storage directory")
            # Remove the path if is not in use. If the tmpfs is in use, the removal will fail.
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                path.rmdir()
                logger.info("Cleaned up storage directory")
            raise RunnerError("Failed to configure runner storage") from err

    @retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
    def _ensure_runner_storage(self, size: int, runner_storage: RunnerStorage) -> Path:
        """Ensure the runner storage is setup.

        Args:
            size: Size of the storage needed in kibibytes.
            runner_storage: Type of storage to use for virtual machine hosting the runners.

        Raises:
            RunnerError: Unable to setup storage for runner.
        """
        match runner_storage:
            case RunnerStorage.MEMORY:
                logger.info("Creating tmpfs storage")
                path = self.ram_pool_path
                self._create_memory_storage(self.ram_pool_path, size)
            case RunnerStorage.JUJU_STORAGE:
                path = self.juju_storage_path

        # tmpfs storage is not created if required size is 0.
        if size > 0:
            # Check if the storage mounted has enough space
            disk = shutil.disk_usage(path)
            # Some storage space might be used by existing runners.
            if size * 1024 > disk.total:
                raise ConfigurationError(
                    (
                        f"Required disk space for runners {size / 1024}MiB is greater than "
                        f"storage total size {disk.total / 1024 / 1024}MiB"
                    )
                )
        return path

    @retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
    def _ensure_service_health(self) -> None:
        """Ensure services managed by the charm is healthy.

        Services managed include:
         * repo-policy-compliance
        """
        logger.info("Checking health of repo-policy-compliance service")
        try:
            execute_command(["/usr/bin/systemctl", "is-active", "repo-policy-compliance"])
        except SubprocessError:
            logger.exception("Found inactive repo-policy-compliance service")
            execute_command(["/usr/bin/systemctl", "restart", "repo-policy-compliance"])
            logger.info("Restart repo-policy-compliance service")
            raise

    def _get_openstack_runner_manager(
        self, state: CharmState, token: str | None = None, path: GithubPath | None = None
    ) -> OpenstackRunnerManager:
        """Get OpenstackRunnerManager instance.

        TODO: Combine this with `_get_runner_manager` during the runner manager interface refactor.

        Args:
            state: Charm state.
            token: GitHub personal access token to manage the runners with. If None the token in
                charm state is used.
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name. If None the path in charm state is used.

        Returns:
            An instance of OpenstackRunnerManager.
        """
        if token is None:
            token = state.charm_config.token
        if path is None:
            path = state.charm_config.path

        app_name, unit = self.unit.name.rsplit("/", 1)
        openstack_runner_manager_config = OpenstackRunnerManagerConfig(
            charm_state=state,
            path=path,
            token=token,
            flavour=state.runner_config.openstack_flavour,
            network=state.runner_config.openstack_network,
            dockerhub_mirror=state.charm_config.dockerhub_mirror,
        )
        return OpenstackRunnerManager(
            app_name,
            unit,
            openstack_runner_manager_config,
            state.charm_config.openstack_clouds_yaml,
        )

    def _get_runner_manager(
        self, state: CharmState, token: str | None = None, path: GithubPath | None = None
    ) -> RunnerManager:
        """Get a RunnerManager instance.

        Args:
            state: Charm state.
            token: GitHub personal access token to manage the runners with. If None the token in
                charm state is used.
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name. If None the path in charm state is used.

        Returns:
            An instance of RunnerManager.
        """
        if token is None:
            token = state.charm_config.token
        if path is None:
            path = state.charm_config.path

        self._ensure_service_health()

        size_in_kib = (
            bytes_with_unit_to_kib(state.runner_config.virtual_machine_resources.disk)
            * state.runner_config.virtual_machines
        )
        lxd_storage_path = self._ensure_runner_storage(
            size_in_kib, state.runner_config.runner_storage
        )

        if self.service_token is None:
            self.service_token = self._get_service_token()

        app_name, unit = self.unit.name.rsplit("/", 1)

        return RunnerManager(
            app_name,
            unit,
            RunnerManagerConfig(
                charm_state=state,
                dockerhub_mirror=state.charm_config.dockerhub_mirror,
                image="jammy",
                lxd_storage_path=lxd_storage_path,
                path=path,
                service_token=self.service_token,
                token=token,
            ),
        )

    @catch_charm_errors
    def _on_install(self, _event: InstallEvent) -> None:
        """Handle the installation of charm.

        Args:
            event: Event of installing the charm.
        """
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            # Only build it in test mode since it may interfere with users systems.
            if self.config.get("test-mode") == "insecure":
                self.unit.status = MaintenanceStatus("Building Openstack image")
                github = GithubClient(token=state.charm_config.token)
                openstack_manager.build_image(
                    arch=state.arch,
                    cloud_config=state.charm_config.openstack_clouds_yaml,
                    github_client=github,
                    path=state.charm_config.path,
                    proxies=state.proxy_config,
                )
                # WIP: Add scheduled building of image during refactor.
                self.unit.status = ActiveStatus()
                return

        self.unit.status = MaintenanceStatus("Installing packages")
        try:
            # The `_start_services`, `_install_deps` includes retry.
            self._install_deps()
            self._start_services(state.charm_config.token, state.proxy_config)
            metrics.setup_logrotate()
        except (LogrotateSetupError, SubprocessError) as err:
            logger.exception(err)
            if isinstance(err, LogrotateSetupError):
                msg = "Failed to setup logrotate"
            else:
                msg = "Failed to install dependencies"
            self.unit.status = BlockedStatus(msg)
            return

        self._refresh_firewall(state)
        runner_manager = self._get_runner_manager(state)

        self.unit.status = MaintenanceStatus("Building runner image")
        runner_manager.build_runner_image()
        runner_manager.schedule_build_runner_image()

        self.unit.status = MaintenanceStatus("Downloading runner binary")
        try:
            runner_info = runner_manager.get_latest_runner_bin_url()
            logger.info(
                "Downloading %s from: %s", runner_info["filename"], runner_info["download_url"]
            )
            self._stored.runner_bin_url = runner_info["download_url"]
            runner_manager.update_runner_bin(runner_info)
        # Safe guard against transient unexpected error.
        except RunnerBinaryError as err:
            logger.exception("Failed to update runner binary")
            # Failure to download runner binary is a transient error.
            # The charm automatically update runner binary on a schedule.
            self.unit.status = MaintenanceStatus(f"Failed to update runner binary: {err}")
            return

        self.unit.status = ActiveStatus()

    @catch_charm_errors
    def _on_start(self, _event: StartEvent) -> None:
        """Handle the start of the charm.

        Args:
            event: Event of starting the charm.
        """
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            runner_manager = self._get_openstack_runner_manager(state)
            runner_manager.reconcile(state.runner_config.virtual_machines)
            self.unit.status = ActiveStatus()
            return

        runner_manager = self._get_runner_manager(state)

        self._check_and_update_dependencies(
            runner_manager, state.charm_config.token, state.proxy_config
        )

        self.unit.status = MaintenanceStatus("Starting runners")
        try:
            runner_manager.flush(FlushMode.FLUSH_IDLE)
            self._reconcile_runners(
                runner_manager,
                state.runner_config.virtual_machines,
                state.runner_config.virtual_machine_resources,
            )
        except RunnerError as err:
            logger.exception("Failed to start runners")
            self.unit.status = MaintenanceStatus(f"Failed to start runners: {err}")
            return

        self.unit.status = ActiveStatus()

    def _update_kernel(self, now: bool = False) -> None:
        """Update the Linux kernel if new version is available.

        Do nothing if no new version is available, else update the kernel and reboot.
        This method should only call by event handlers, and not action handlers. As juju-reboot
        only works with events.

        Args:
            now: Whether the reboot should trigger at end of event handler or now.
        """
        logger.info("Upgrading kernel")
        self._apt_install(["linux-generic"])

        _, exit_code = execute_command(["ls", "/var/run/reboot-required"], check_exit=False)
        if exit_code == 0:
            logger.info("Rebooting system...")
            self.unit.reboot(now=now)

    def _set_reconcile_timer(self) -> None:
        """Set the timer for regular reconciliation checks."""
        self._event_timer.ensure_event_timer(
            event_name="reconcile-runners",
            interval=int(self.config["reconcile-interval"]),
            timeout=int(self.config["reconcile-interval"]) - 1,
        )

    def _ensure_reconcile_timer_is_active(self) -> None:
        """Ensure the timer for reconciliation event is active."""
        try:
            reconcile_timer_is_active = self._event_timer.is_active(RECONCILE_RUNNERS_EVENT)
        except TimerStatusError:
            logger.exception("Failed to check the reconciliation event timer status")
        else:
            if not reconcile_timer_is_active:
                logger.error("Reconciliation event timer is not activated")
                self._set_reconcile_timer()

    @catch_charm_errors
    def _on_upgrade_charm(self, _event: UpgradeCharmEvent) -> None:
        """Handle the update of charm.

        Args:
            event: Event of charm upgrade.
        """
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            # No dependency upgrade needed for openstack.
            # No need to flush runners as there was no dependency upgrade.
            return

        logger.info("Reinstalling dependencies...")
        try:
            # The `_start_services`, `_install_deps` includes retry.
            self._install_deps()
            self._start_services(state.charm_config.token, state.proxy_config)
            metrics.setup_logrotate()
        except (LogrotateSetupError, SubprocessError) as err:
            logger.exception(err)

            if isinstance(err, LogrotateSetupError):
                msg = "Failed to setup logrotate"
            else:
                msg = "Failed to install dependencies"
            self.unit.status = BlockedStatus(msg)
            return

        state = self._setup_state()
        self._refresh_firewall(state)
        logger.info("Flushing the runners...")
        runner_manager = self._get_runner_manager(state)
        if not runner_manager:
            return

        runner_manager.flush(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
        self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )

    @catch_charm_errors
    def _on_config_changed(self, _event: ConfigChangedEvent) -> None:
        """Handle the configuration change.

        Args:
            event: Event of configuration change.
        """
        state = self._setup_state()
        self._set_reconcile_timer()

        prev_config_for_flush: dict[str, str] = {}
        should_flush_runners = False
        if state.charm_config.token != self._stored.token:
            prev_config_for_flush["token"] = str(self._stored.token)
            self._start_services(state.charm_config.token, state.proxy_config)
            self._stored.token = None
        if self.config["path"] != self._stored.path:
            prev_config_for_flush["path"] = parse_github_path(
                self._stored.path, self.config["group"]
            )
            self._stored.path = self.config["path"]
        if self.config[LABELS_CONFIG_NAME] != self._stored.labels:
            should_flush_runners = True
            self._stored.labels = self.config[LABELS_CONFIG_NAME]
        if prev_config_for_flush or should_flush_runners:
            if state.instance_type != InstanceType.OPENSTACK:
                prev_runner_manager = self._get_runner_manager(
                    state=state, **prev_config_for_flush
                )
                if prev_runner_manager:
                    self.unit.status = MaintenanceStatus("Removing runners due to config change")
                    # it may be the case that the prev token has expired, so we need to use force flush
                    prev_runner_manager.flush(FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK)

        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            runner_manager = self._get_openstack_runner_manager(state)
            runner_manager.reconcile(state.runner_config.virtual_machines)
            self.unit.status = ActiveStatus()
            return

        self._refresh_firewall(state)

        runner_manager = self._get_runner_manager(state)
        self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )
        if state.charm_config.token != self._stored.token:
            runner_manager.flush(FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK)
            self._stored.token = state.charm_config.token

        self.unit.status = ActiveStatus()

    def _check_and_update_dependencies(
        self, runner_manager: RunnerManager, token: str, proxy_config: ProxyConfig
    ) -> bool:
        """Check and updates runner binary and services.

        The runners are flushed if needed.

        Args:
            runner_manager: RunnerManager used for finding the runner application to download.
            token: GitHub personal access token for repo-policy-compliance to use.
            proxy_config: Proxy configuration.

        Returns:
            Whether the runner binary or the services was updated.
        """
        self.unit.status = MaintenanceStatus("Checking for updates")

        # Check if the runner binary file exists.
        if not runner_manager.check_runner_bin():
            self._stored.runner_bin_url = None
        try:
            self.unit.status = MaintenanceStatus("Checking for runner binary updates")
            runner_info = runner_manager.get_latest_runner_bin_url()
        except urllib.error.URLError as err:
            logger.exception("Failed to check for runner updates")
            # Failure to download runner binary is a transient error.
            # The charm automatically update runner binary on a schedule.
            self.unit.status = MaintenanceStatus(f"Failed to check for runner updates: {err}")
            return False

        logger.debug(
            "Current runner binary URL: %s, Queried runner binary URL: %s",
            self._stored.runner_bin_url,
            runner_info.download_url,
        )
        runner_bin_updated = False
        if runner_info.download_url != self._stored.runner_bin_url:
            self.unit.status = MaintenanceStatus("Updating runner binary")
            runner_manager.update_runner_bin(runner_info)
            self._stored.runner_bin_url = runner_info.download_url
            runner_bin_updated = True

        self.unit.status = MaintenanceStatus("Checking for service updates")
        service_updated = self._install_repo_policy_compliance(proxy_config)

        if service_updated or runner_bin_updated:
            logger.info(
                "Flushing runner due to: service updated=%s, runner binary update=%s",
                service_updated,
                runner_bin_updated,
            )
            self.unit.status = MaintenanceStatus("Flushing runners due to updated deps")
            runner_manager.flush(FlushMode.FLUSH_IDLE_WAIT_REPO_CHECK)
            self._start_services(token, proxy_config)

        self.unit.status = ActiveStatus()
        return service_updated or runner_bin_updated

    @catch_charm_errors
    def _on_reconcile_runners(self, _event: ReconcileRunnersEvent) -> None:
        """Handle the reconciliation of runners.

        Args:
            event: Event of reconciling the runner state.
        """
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            runner_manager = self._get_openstack_runner_manager(state)
            runner_manager.reconcile(state.runner_config.virtual_machines)
            self.unit.status = ActiveStatus()
            return

        runner_manager = self._get_runner_manager(state)

        self._check_and_update_dependencies(
            runner_manager, state.charm_config.token, state.proxy_config
        )

        runner_info = runner_manager.get_github_info()
        if all(not info.busy for info in runner_info):
            self._update_kernel(now=True)

        self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )

        self.unit.status = ActiveStatus()

    @catch_action_errors
    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state."""
        online = 0
        offline = 0
        unknown = 0
        runner_names = []

        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            openstack_runner_manager = self._get_openstack_runner_manager(state)
            runner_info = openstack_runner_manager.get_github_runner_info()

            for info in runner_info:
                if info.online:
                    online += 1
                    runner_names.append(info.runner_name)
                else:
                    offline += 1
            event.set_results(
                {
                    "online": online,
                    "offline": offline,
                    "unknown": unknown,
                    "runners": ", ".join(runner_names),
                }
            )
            return

        runner_manager = self._get_runner_manager(state)
        if runner_manager.runner_bin_path is None:
            event.fail("Missing runner binary")
            return

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
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            runner_manager = self._get_openstack_runner_manager(state)

            delta = runner_manager.reconcile(state.runner_config.virtual_machines)
            event.set_results(delta)
            return

        runner_manager = self._get_runner_manager(state)

        self._check_and_update_dependencies(
            runner_manager, state.charm_config.token, state.proxy_config
        )

        delta = self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )
        self._on_check_runners_action(event)
        event.set_results(delta)

    @catch_action_errors
    def _on_flush_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of flushing all runner and reconciling afterwards.

        Args:
            event: Action event of flushing all runners.
        """
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            # Flushing not implemented for OpenStack.
            raise NotImplementedError()

        runner_manager = self._get_runner_manager(state)

        runner_manager.flush(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
        delta = self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )

        self._on_check_runners_action(event)
        event.set_results(delta)

    @catch_action_errors
    def _on_update_dependencies_action(self, event: ActionEvent) -> None:
        """Handle the action of updating dependencies and flushing runners if needed.

        Args:
            event: Action event of updating dependencies.
        """
        state = self._setup_state()
        if state.instance_type == InstanceType.OPENSTACK:
            # No dependencies managed by the charm for OpenStack-based runners.
            event.set_results({"flush": False})

        runner_manager = self._get_runner_manager(state)
        flushed = self._check_and_update_dependencies(
            runner_manager, state.charm_config.token, state.proxy_config
        )
        event.set_results({"flush": flushed})

    @catch_charm_errors
    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Handle the update of charm status.

        Args:
            event: Event of updating the charm status.
        """
        self._ensure_reconcile_timer_is_active()

    @catch_charm_errors
    def _on_stop(self, _: StopEvent) -> None:
        """Handle the stopping of the charm.

        Args:
            event: Event of stopping the charm.
        """
        self._event_timer.disable_event_timer("reconcile-runners")
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            # Flushing not implemented for OpenStack.
            raise NotImplementedError()

        runner_manager = self._get_runner_manager(state)
        runner_manager.flush(FlushMode.FLUSH_BUSY)

    def _reconcile_runners(
        self, runner_manager: RunnerManager, num: int, resources: VirtualMachineResources
    ) -> Dict[str, Any]:
        """Reconcile the current runners state and intended runner state.

        Args:
            runner_manager: For querying and managing the runner state.
            num: Target number of virtual machines.
            resource: Target resource for each virtual machine.

        Returns:
            Changes in runner number due to reconciling runners.
        """
        if not RunnerManager.runner_bin_path.is_file():
            logger.warning("Unable to reconcile due to missing runner binary")
            raise MissingRunnerBinaryError()

        self.unit.status = MaintenanceStatus("Reconciling runners")
        delta_virtual_machines = runner_manager.reconcile(
            num,
            resources,
        )

        self.unit.status = ActiveStatus()
        return {"delta": {"virtual-machines": delta_virtual_machines}}

    def _install_repo_policy_compliance(self, proxy_config: ProxyConfig) -> bool:
        """Install latest version of repo_policy_compliance service.

        Args:
            proxy_config: Proxy configuration.

        Returns:
            Whether version install is changed. Going from not installed to
            installed will return True.
        """
        # Prepare environment variables for pip subprocess
        env = {}
        if http_proxy := proxy_config.http:
            env["HTTP_PROXY"] = http_proxy
            env["http_proxy"] = http_proxy
        if https_proxy := proxy_config.https:
            env["HTTPS_PROXY"] = https_proxy
            env["https_proxy"] = https_proxy
        if no_proxy := proxy_config.no_proxy:
            env["NO_PROXY"] = no_proxy
            env["no_proxy"] = no_proxy

        old_version = execute_command(
            [
                "/usr/bin/python3",
                "-m",
                "pip",
                "show",
                "repo-policy-compliance",
            ],
            check_exit=False,
        )

        execute_command(
            [
                "/usr/bin/python3",
                "-m",
                "pip",
                "install",
                "--upgrade",
                "git+https://github.com/canonical/repo-policy-compliance@main",
            ],
            env=env,
        )

        new_version = execute_command(
            [
                "/usr/bin/python3",
                "-m",
                "pip",
                "show",
                "repo-policy-compliance",
            ],
            check_exit=False,
        )
        return old_version != new_version

    def _enable_kernel_modules(self) -> None:
        """Enable kernel modules needed by the charm."""
        execute_command(["/usr/sbin/modprobe", "br_netfilter"])
        with self.kernel_module_path.open("a", encoding="utf-8") as modules_file:
            modules_file.write("br_netfilter\n")

    @retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
    def _install_deps(self) -> None:
        """Install dependencies."""
        state = self._setup_state()

        logger.info("Installing charm dependencies.")
        # Snap and Apt will use any proxies configured in the Juju model.
        # Binding for snap, apt, and lxd init commands are not available so subprocess.run used.
        # Install dependencies used by repo-policy-compliance and the firewall
        self._apt_install(["gunicorn", "python3-pip", "nftables"])
        # Install repo-policy-compliance package
        self._install_repo_policy_compliance(state.proxy_config)
        execute_command(
            ["/usr/bin/apt-get", "remove", "-qy", "lxd", "lxd-client"], check_exit=False
        )
        self._apt_install(
            [
                "cpu-checker",
                "libvirt-clients",
                "libvirt-daemon-driver-qemu",
                "apparmor-utils",
            ],
        )
        execute_command(["/usr/bin/snap", "install", "lxd", "--channel=latest/stable"])
        execute_command(["/usr/bin/snap", "refresh", "lxd", "--channel=latest/stable"])
        # Add ubuntu user to lxd group, to allow building images with ubuntu user
        execute_command(["/usr/sbin/usermod", "-aG", "lxd", "ubuntu"])
        execute_command(["/snap/bin/lxd", "waitready"])
        execute_command(["/snap/bin/lxd", "init", "--auto"])
        execute_command(["/snap/bin/lxc", "network", "set", "lxdbr0", "ipv6.address", "none"])
        execute_command(["/snap/bin/lxd", "waitready"])
        if not LXD_PROFILE_YAML.exists():
            self._enable_kernel_modules()
        execute_command(
            [
                "/snap/bin/lxc",
                "profile",
                "device",
                "set",
                "default",
                "eth0",
                "security.ipv4_filtering=true",
                "security.ipv6_filtering=true",
                "security.mac_filtering=true",
                "security.port_isolation=true",
            ]
        )
        logger.info("Finished installing charm dependencies.")

    @retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
    def _start_services(self, token: str, proxy_config: ProxyConfig) -> None:
        """Ensure all services managed by the charm is running.

        Args:
            token: GitHub personal access token for repo-policy-compliance to use.
            proxy_config: Proxy configuration.
        """
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
            github_token=token,
            proxies=proxy_config,
        )
        self.repo_check_systemd_service.write_text(service_content, encoding="utf-8")

        execute_command(["/usr/bin/systemctl", "daemon-reload"])
        execute_command(["/usr/bin/systemctl", "restart", "repo-policy-compliance"])
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

    def _refresh_firewall(self, state: CharmState) -> None:
        """Refresh the firewall configuration and rules.

        Args:
            state: Charm state.
        """
        # Temp: Monitor the LXD networks to track down issues with missing network.
        logger.info(execute_command(["/snap/bin/lxc", "network", "list", "--format", "json"]))

        allowlist = [
            FirewallEntry.decode(str(entry.host)) for entry in state.ssh_debug_connections
        ]
        firewall = Firewall("lxdbr0")
        firewall.refresh_firewall(denylist=state.charm_config.denylist, allowlist=allowlist)
        logger.debug(
            "firewall update, current firewall: %s",
            execute_command(["/usr/sbin/nft", "list", "ruleset"]),
        )

    def _apt_install(self, packages: Sequence[str]) -> None:
        execute_command(["/usr/bin/apt-get", "update"])

        _, exit_code = execute_command(
            ["/usr/bin/apt-get", "install", "-qy"] + list(packages), check_exit=False
        )
        if exit_code == 100:
            logging.warning("Running 'dpkg --configure -a' as last apt install was interrupted")
            execute_command(["dpkg", "--configure", "-a"])
            execute_command(["/usr/bin/apt-get", "install", "-qy"] + list(packages))

    @catch_charm_errors
    def _on_debug_ssh_relation_changed(self, _: ops.RelationChangedEvent) -> None:
        """Handle debug ssh relation changed event."""
        state = self._setup_state()

        if state.instance_type == InstanceType.OPENSTACK:
            # Flushing not implemented for OpenStack.
            raise NotImplementedError()

        self._refresh_firewall(state)
        runner_manager = self._get_runner_manager(state)
        runner_manager.flush(FlushMode.FLUSH_IDLE)
        self._reconcile_runners(
            runner_manager,
            state.runner_config.virtual_machines,
            state.runner_config.virtual_machine_resources,
        )


if __name__ == "__main__":
    main(GithubRunnerCharm)
