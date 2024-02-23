#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for creating and managing GitHub self-hosted runner instances."""

import functools
import logging
import os
import secrets
import shutil
import urllib.error
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar
from urllib.parse import urlsplit

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
import openstack_manager
from charm_state import DEBUG_SSH_INTEGRATION_NAME, CharmConfigInvalidError, RunnerStorage, State
from errors import (
    ConfigurationError,
    LogrotateSetupError,
    MissingConfigurationError,
    MissingRunnerBinaryError,
    OpenStackUnauthorizedError,
    RunnerBinaryError,
    RunnerError,
    SubprocessError,
    TokenError,
)
from event_timer import EventTimer, TimerStatusError
from firewall import Firewall, FirewallEntry
from github_type import GitHubRunnerStatus
from runner import LXD_PROFILE_YAML
from runner_manager import RunnerManager, RunnerManagerConfig
from runner_manager_type import FlushMode
from runner_type import GithubOrg, GithubRepo, ProxySetting, VirtualMachineResources
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
        except MissingConfigurationError as err:
            logger.exception("Missing required charm configuration")
            self.unit.status = BlockedStatus(
                f"Missing required charm configuration: {err.configs}"
            )
        except MissingRunnerBinaryError:
            logger.exception("Missing runner binary")
            self.unit.status = MaintenanceStatus(
                "Missing runner binary, automatic retry will be attempted"
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
        except MissingConfigurationError as err:
            logger.exception("Missing required charm configuration")
            event.fail(f"Missing required charm configuration: {err.configs}")
        except MissingRunnerBinaryError:
            logger.exception("Missing runner binary")
            self.unit.status = MaintenanceStatus(
                "Missing runner binary, automatic retry will be attempted"
            )

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

    def __init__(self, *args, **kargs) -> None:
        """Construct the charm.

        Args:
            args: List of arguments to be passed to the `CharmBase` class.
            kargs: List of keyword arguments to be passed to the `CharmBase`
                class.
        """
        super().__init__(*args, **kargs)

        self._grafana_agent = COSAgentProvider(self)

        try:
            self._state = State.from_charm(self)
        except CharmConfigInvalidError as exc:
            self.unit.status = ops.BlockedStatus(exc.msg)
            return

        self._event_timer = EventTimer(self.unit.name)

        if LXD_PROFILE_YAML.exists():
            if self.config.get("test-mode") != "insecure":
                raise RuntimeError("lxd-profile.yaml detected outside test mode")
            logger.critical("test mode is enabled")

        self._stored.set_default(
            path=self.config["path"],  # for detecting changes
            token=self.config["token"],  # for detecting changes
            runner_bin_url=None,
        )

        self.proxies: ProxySetting = {}
        if proxy_config := self._state.proxy_config:
            if http_proxy := proxy_config.http_proxy:
                self.proxies["http"] = str(http_proxy)
            if https_proxy := proxy_config.https_proxy:
                self.proxies["https"] = str(https_proxy)
            # there's no need for no_proxy if there's no http_proxy or https_proxy
            no_proxy = proxy_config.no_proxy
            if (https_proxy or http_proxy) and no_proxy:
                self.proxies["no_proxy"] = no_proxy
            if proxy_config.use_aproxy:
                self.proxies["aproxy_address"] = proxy_config.aproxy_address

        self.service_token = None

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

    @retry(tries=5, delay=15, max_delay=60, backoff=1.5, local_logger=logger)
    def _ensure_runner_storage(self, size: int) -> Path:
        """Ensure the runner storage is setup.

        Args:
            size: Size of the storage needed in kibibytes.

        Raises:
            RunnerError: Unable to setup storage for runner.
        """
        match self._state.charm_config.runner_storage:
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

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5, local_logger=logger)
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

    def _get_runner_manager(
        self, token: Optional[str] = None, path: Optional[str] = None
    ) -> RunnerManager:
        """Get a RunnerManager instance, or None if missing config.

        Args:
            token: GitHub personal access token to manager the runners with.
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name.

        Returns:
            An instance of RunnerManager.
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

        dockerhub_mirror = self.config["dockerhub-mirror"] or None
        dockerhub_mirror_url = urlsplit(dockerhub_mirror)
        if dockerhub_mirror is not None and dockerhub_mirror_url.scheme != "https":
            raise ConfigurationError(
                "Only secured registry supported for dockerhub mirror, the scheme should be https"
            )

        self._ensure_service_health()

        size_in_kib = (
            bytes_with_unit_to_kib(self.config["vm-disk"]) * self.config["virtual-machines"]
        )

        lxd_storage_path = self._ensure_runner_storage(size_in_kib)

        if self.service_token is None:
            self.service_token = self._get_service_token()

        if "/" in path:
            paths = path.split("/")
            if len(paths) != 2:
                logger.error("Invalid path %s", path)
                raise ConfigurationError(f"Invalid path {path}")

            owner, repo = paths
            path = GithubRepo(owner=owner, repo=repo)
        else:
            path = GithubOrg(org=path, group=self.config["group"])

        app_name, unit = self.unit.name.rsplit("/", 1)
        return RunnerManager(
            app_name,
            unit,
            RunnerManagerConfig(
                path=path,
                token=token,
                image="jammy",
                service_token=self.service_token,
                lxd_storage_path=lxd_storage_path,
                charm_state=self._state,
                dockerhub_mirror=dockerhub_mirror,
            ),
            proxies=self.proxies,
        )

    @catch_charm_errors
    def _on_install(self, _event: InstallEvent) -> None:
        """Handle the installation of charm.

        Args:
            event: Event of installing the charm.
        """
        self.unit.status = MaintenanceStatus("Installing packages")

        try:
            # The `_start_services`, `_install_deps` includes retry.
            self._install_deps()
            self._start_services()
            metrics.setup_logrotate()
        except (LogrotateSetupError, SubprocessError) as err:
            logger.exception(err)

            if isinstance(err, LogrotateSetupError):
                msg = "Failed to setup logrotate"
            else:
                msg = "Failed to install dependencies"
            self.unit.status = BlockedStatus(msg)
            return

        self._refresh_firewall()
        runner_manager = self._get_runner_manager()

        self.unit.status = MaintenanceStatus("Building runner image")
        runner_manager.build_runner_image()
        runner_manager.schedule_build_runner_image()

        self.unit.status = MaintenanceStatus("Downloading runner binary")
        try:
            runner_info = runner_manager.get_latest_runner_bin_url()
            logger.info("Downloading %s from: %s", runner_info.filename, runner_info.download_url)
            self._stored.runner_bin_url = runner_info.download_url
            runner_manager.update_runner_bin(runner_info)
        # Safe guard against transient unexpected error.
        except RunnerBinaryError as err:
            logger.exception("Failed to update runner binary")
            # Failure to download runner binary is a transient error.
            # The charm automatically update runner binary on a schedule.
            self.unit.status = MaintenanceStatus(f"Failed to update runner binary: {err}")
            return

        self.unit.status = ActiveStatus()

    def _on_start(self, _event: StartEvent) -> None:
        """Handle the start of the charm.

        Args:
            event: Event of starting the charm.
        """
        self._check_and_update_dependencies()

        runner_manager = self._get_runner_manager()

        self.unit.status = MaintenanceStatus("Starting runners")
        try:
            runner_manager.flush(FlushMode.FLUSH_IDLE)
            self._reconcile_runners(runner_manager)
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
        logger.info("Reinstalling dependencies...")
        try:
            # The `_start_services`, `_install_deps` includes retry.
            self._install_deps()
            self._start_services()
            metrics.setup_logrotate()
        except (LogrotateSetupError, SubprocessError) as err:
            logger.exception(err)

            if isinstance(err, LogrotateSetupError):
                msg = "Failed to setup logrotate"
            else:
                msg = "Failed to install dependencies"
            self.unit.status = BlockedStatus(msg)
            return
        self._refresh_firewall()

        logger.info("Flushing the runners...")
        runner_manager = self._get_runner_manager()
        if not runner_manager:
            return

        runner_manager.flush(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
        self._reconcile_runners(runner_manager)

    @catch_charm_errors
    def _on_config_changed(self, _event: ConfigChangedEvent) -> None:
        """Handle the configuration change.

        Args:
            event: Event of configuration change.
        """
        self._set_reconcile_timer()

        prev_config_for_flush: dict[str, str] = {}

        if self.config["token"] != self._stored.token:
            prev_config_for_flush["token"] = str(self._stored.token)
            self._start_services()
            self._stored.token = None

        if self.config["path"] != self._stored.path:
            prev_config_for_flush["path"] = str(self._stored.path)
            self._stored.path = self.config["path"]

        if prev_config_for_flush:
            prev_runner_manager = self._get_runner_manager(**prev_config_for_flush)
            if prev_runner_manager:
                self.unit.status = MaintenanceStatus("Removing runners due to config change")
                # it may be the case that the prev token has expired, so we need to use force flush
                prev_runner_manager.flush(FlushMode.FORCE_FLUSH_WAIT_REPO_CHECK)

        self._refresh_firewall()

        if self._state.charm_config.openstack_clouds_yaml:
            image = openstack_manager.build_image(
                self._state.charm_config.openstack_clouds_yaml, self.proxies
            )
            logger.info("Image successfully built: %s", image)
            # Test out openstack integration and then go
            # into BlockedStatus as it is not supported yet
            projects = openstack_manager.list_projects(
                self._state.charm_config.openstack_clouds_yaml
            )
            logger.info("OpenStack projects: %s", projects)
            self.unit.status = BlockedStatus(
                "OpenStack integration is not supported yet. "
                "Please remove the openstack-clouds-yaml config."
            )
            return

        try:
            runner_manager = self._get_runner_manager()
        except MissingConfigurationError as err:
            self.unit.status = BlockedStatus(
                f"Missing required charm configuration: {err.configs}"
            )
        else:
            self._reconcile_runners(runner_manager)
            self.unit.status = ActiveStatus()

        if self.config["token"] != self._stored.token:
            self._stored.token = self.config["token"]

    def _check_and_update_dependencies(self) -> bool:
        """Check and updates runner binary and services.

        The runners are flushed if needed.

        Returns:
            Whether the runner binary or the services was updated.
        """
        self.unit.status = MaintenanceStatus("Checking for updates")

        runner_manager = self._get_runner_manager()

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
        service_updated = self._install_repo_policy_compliance()

        if service_updated or runner_bin_updated:
            logger.info(
                "Flushing runner due to: service updated=%s, runner binary update=%s",
                service_updated,
                runner_bin_updated,
            )

            self.unit.status = MaintenanceStatus("Flushing runners due to updated deps")

            runner_manager.flush(FlushMode.FLUSH_IDLE_WAIT_REPO_CHECK)
            self._start_services()

        self.unit.status = ActiveStatus()
        return service_updated or runner_bin_updated

    @catch_charm_errors
    def _on_reconcile_runners(self, _event: ReconcileRunnersEvent) -> None:
        """Handle the reconciliation of runners.

        Args:
            event: Event of reconciling the runner state.
        """
        self._check_and_update_dependencies()

        runner_manager = self._get_runner_manager()

        runner_info = runner_manager.get_github_info()
        if all(not info.busy for info in runner_info):
            self._update_kernel(now=True)

        self._reconcile_runners(runner_manager)

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
        self._check_and_update_dependencies()

        runner_manager = self._get_runner_manager()

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

        runner_manager.flush(FlushMode.FLUSH_BUSY_WAIT_REPO_CHECK)
        delta = self._reconcile_runners(runner_manager)

        self._on_check_runners_action(event)
        event.set_results(delta)

    @catch_action_errors
    def _on_update_dependencies_action(self, event: ActionEvent) -> None:
        """Handle the action of updating dependencies and flushing runners if needed.

        Args:
            event: Action event of updating dependencies.
        """
        flushed = self._check_and_update_dependencies()
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

        runner_manager = self._get_runner_manager()
        runner_manager.flush(FlushMode.FLUSH_BUSY)

    def _reconcile_runners(self, runner_manager: RunnerManager) -> Dict[str, Any]:
        """Reconcile the current runners state and intended runner state.

        Args:
            runner_manager: For querying and managing the runner state.

        Returns:
            Changes in runner number due to reconciling runners.
        """
        if not RunnerManager.runner_bin_path.is_file():
            logger.warning("Unable to reconcile due to missing runner binary")
            raise MissingRunnerBinaryError()

        self.unit.status = MaintenanceStatus("Reconciling runners")

        virtual_machines_resources = VirtualMachineResources(
            self.config["vm-cpu"], self.config["vm-memory"], self.config["vm-disk"]
        )

        virtual_machines = self.config["virtual-machines"]

        delta_virtual_machines = runner_manager.reconcile(
            virtual_machines, virtual_machines_resources
        )

        self.unit.status = ActiveStatus()

        return {"delta": {"virtual-machines": delta_virtual_machines}}

    def _install_repo_policy_compliance(self) -> bool:
        """Install latest version of repo_policy_compliance service.

        Returns:
            Whether version install is changed. Going from not installed to
            installed will return True.
        """
        # Prepare environment for pip subprocess
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

        with open("/etc/modules", "a", encoding="utf-8") as modules_file:
            modules_file.write("br_netfilter\n")

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5, local_logger=logger)
    def _install_deps(self) -> None:
        """Install dependencies."""
        logger.info("Installing charm dependencies.")

        # Snap and Apt will use any proxies configured in the Juju model.
        # Binding for snap, apt, and lxd init commands are not available so subprocess.run used.
        # Install dependencies used by repo-policy-compliance and the firewall
        self._apt_install(["gunicorn", "python3-pip", "nftables"])

        # Install repo-policy-compliance package
        self._install_repo_policy_compliance()

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

    @retry(tries=10, delay=15, max_delay=60, backoff=1.5, local_logger=logger)
    def _start_services(self) -> None:
        """Ensure all services managed by the charm is running."""
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

    def _refresh_firewall(self):
        """Refresh the firewall configuration and rules."""
        # Temp: Monitor the LXD networks to track down issues with missing network.
        logger.info(execute_command(["/snap/bin/lxc", "network", "list", "--format", "json"]))

        firewall_denylist_config = self.config.get("denylist")
        denylist = []
        if firewall_denylist_config.strip():
            denylist = [
                FirewallEntry.decode(entry.strip())
                for entry in firewall_denylist_config.split(",")
            ]
        allowlist = [
            FirewallEntry.decode(str(entry.host)) for entry in self._state.ssh_debug_connections
        ]
        firewall = Firewall("lxdbr0")
        firewall.refresh_firewall(denylist=denylist, allowlist=allowlist)
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

    def _on_debug_ssh_relation_changed(self, _: ops.RelationChangedEvent) -> None:
        """Handle debug ssh relation changed event."""
        self._refresh_firewall()
        runner_manager = self._get_runner_manager()
        runner_manager.flush(FlushMode.FLUSH_IDLE)
        self._reconcile_runners(runner_manager)


if __name__ == "__main__":
    main(GithubRunnerCharm)
