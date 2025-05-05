#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for creating and managing GitHub self-hosted runner instances."""
from manager_client import GitHubRunnerManagerClient
from utilities import execute_command, remove_residual_venv_dirs

# This is a workaround for https://bugs.launchpad.net/juju/+bug/2058335
# It is important that this is run before importation of any other modules.
# pylint: disable=wrong-import-position,wrong-import-order
# TODO: 2024-07-17 remove this once the issue has been fixed
remove_residual_venv_dirs()


import functools
import json
import logging
import pathlib
from typing import Any, Callable, Sequence, TypeVar

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from github_runner_manager import constants
from github_runner_manager.errors import ReconcileError
from github_runner_manager.manager.runner_manager import FlushMode
from github_runner_manager.manager.runner_scaler import RunnerScaler
from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    EventBase,
    InstallEvent,
    StartEvent,
    StopEvent,
    UpdateStatusEvent,
    UpgradeCharmEvent,
)
from ops.framework import StoredState
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

import logrotate
import manager_service
from charm_state import (
    DEBUG_SSH_INTEGRATION_NAME,
    IMAGE_INTEGRATION_NAME,
    LABELS_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    CharmConfigInvalidError,
    CharmState,
    OpenstackImage,
)
from errors import (
    ConfigurationError,
    LogrotateSetupError,
    MissingMongoDBError,
    RunnerManagerApplicationError,
    RunnerManagerApplicationInstallError,
    RunnerManagerServiceError,
    SubprocessError,
    TokenError,
)
from event_timer import EventTimer, TimerStatusError
from factories import create_runner_scaler

# We assume a stuck reconcile event when it takes longer
# than 10 times a normal interval. Currently, we are only aware of
# https://bugs.launchpad.net/juju/+bug/2055184 causing a stuck reconcile event.
RECONCILIATION_INTERVAL_TIMEOUT_FACTOR = 10
RECONCILE_RUNNERS_EVENT = "reconcile-runners"

# This is currently hardcoded and may be moved to a config option in the future.
REACTIVE_MQ_DB_NAME = "github-runner-webhook-router"


ACTIVE_STATUS_RECONCILIATION_FAILED_MSG = "Last reconciliation failed."
FAILED_TO_RECONCILE_RUNNERS_MSG = "Failed to reconcile runners"
FAILED_RECONCILE_ACTION_ERR_MSG = (
    "Failed to reconcile runners. Look at the juju logs for more information."
)
UPGRADE_MSG = "Upgrading github-runner charm."


logger = logging.getLogger(__name__)


class ReconcileRunnersEvent(EventBase):
    """Event representing a periodic check to ensure runners are ok."""


EventT = TypeVar("EventT")


def catch_charm_errors(
    func: Callable[["GithubRunnerCharm", EventT], None],
) -> Callable[["GithubRunnerCharm", EventT], None]:
    """Catch common errors in charm.

    Args:
        func: Charm function to be decorated.

    Returns:
        Decorated charm function with catching common errors.
    """

    @functools.wraps(func)
    # flake8 thinks the event argument description is missing in the docstring.
    def func_with_catch_errors(self: "GithubRunnerCharm", event: EventT) -> None:
        """Handle errors raised while handling charm events.

        Args:
            event: The charm event to handle.
        """  # noqa: D417
        try:
            func(self, event)
        except ConfigurationError as err:
            logger.exception("Issue with charm configuration")
            self.unit.status = BlockedStatus(str(err))
        except TokenError as err:
            logger.exception("Issue with GitHub token")
            self.unit.status = BlockedStatus(str(err))
        except MissingMongoDBError as err:
            logger.exception("Missing integration data")
            self.unit.status = WaitingStatus(str(err))

    return func_with_catch_errors


def catch_action_errors(
    func: Callable[["GithubRunnerCharm", ActionEvent], None],
) -> Callable[["GithubRunnerCharm", ActionEvent], None]:
    """Catch common errors in actions.

    Args:
        func: Action function to be decorated.

    Returns:
        Decorated charm function with catching common errors.
    """

    @functools.wraps(func)
    # flake8 thinks the event argument description is missing in the docstring.
    def func_with_catch_errors(self: "GithubRunnerCharm", event: ActionEvent) -> None:
        """Handle errors raised while handling events.

        Args:
            event: The action event to catch for errors.
        """  # noqa: D417
        try:
            func(self, event)
        except ConfigurationError as err:
            logger.exception("Issue with charm configuration")
            self.unit.status = BlockedStatus(str(err))
            event.fail(str(err))

    return func_with_catch_errors


class GithubRunnerCharm(CharmBase):
    """Charm for managing GitHub self-hosted runners."""

    _stored = StoredState()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Construct the charm.

        Args:
            args: List of arguments to be passed to the `CharmBase` class.
            kwargs: List of keyword arguments to be passed to the `CharmBase`
                class.
        """
        super().__init__(*args, **kwargs)
        self._log_charm_status()

        self._grafana_agent = COSAgentProvider(self)

        self._event_timer = EventTimer(self.unit.name)

        self._stored.set_default(
            path=self.config[PATH_CONFIG_NAME],  # for detecting changes
            token=self.config[TOKEN_CONFIG_NAME],  # for detecting changes
            labels=self.config[LABELS_CONFIG_NAME],  # for detecting changes
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
        self.framework.observe(
            self.on[IMAGE_INTEGRATION_NAME].relation_joined,
            self._on_image_relation_joined,
        )
        self.framework.observe(
            self.on[IMAGE_INTEGRATION_NAME].relation_changed,
            self._on_image_relation_changed,
        )
        self.framework.observe(self.on.reconcile_runners, self._on_reconcile_runners)
        self.framework.observe(self.on.check_runners_action, self._on_check_runners_action)
        self.framework.observe(self.on.reconcile_runners_action, self._on_reconcile_runners_action)
        self.framework.observe(self.on.flush_runners_action, self._on_flush_runners_action)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.database = DatabaseRequires(
            self, relation_name="mongodb", database_name=REACTIVE_MQ_DB_NAME
        )
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)

        self._manager_client = GitHubRunnerManagerClient(
            host=manager_service.GITHUB_RUNNER_MANAGER_ADDRESS,
            port=manager_service.GITHUB_RUNNER_MANAGER_PORT,
        )

    def _setup_state(self) -> CharmState:
        """Set up the charm state.

        Raises:
            ConfigurationError: If an invalid charm state has set.

        Returns:
            The charm state.
        """
        try:
            return CharmState.from_charm(charm=self, database=self.database)
        except CharmConfigInvalidError as exc:
            raise ConfigurationError(exc.msg) from exc

    def _common_install_code(self) -> bool:
        """Installation code shared between install and upgrade hook.

        Raises:
            LogrotateSetupError: Failed to setup logrotate.
            SubprocessError: Failed to install dependencies.

        Returns:
            True if installation was successful, False otherwise.
        """
        try:
            self._install_deps()
        except SubprocessError:
            logger.error("Failed to install charm dependencies")
            raise

        try:
            _setup_runner_manager_user()
        except SubprocessError:
            logger.error("Failed to setup runner manager user")
            raise

        try:
            manager_service.install_package()
        except RunnerManagerApplicationInstallError:
            logger.error("Failed to install github runner manager package")
            # Not re-raising error for until the github-runner-manager service replaces the
            # library.

        try:
            logrotate.setup()
        except LogrotateSetupError:
            logger.error("Failed to setup logrotate")
            raise

        return True

    @catch_charm_errors
    def _on_install(self, _: InstallEvent) -> None:
        """Handle the installation of charm."""
        self._common_install_code()

    @catch_charm_errors
    def _on_start(self, _: StartEvent) -> None:
        """Handle the start of the charm."""
        state = self._setup_state()

        self.unit.status = MaintenanceStatus("Starting runners")
        if not self._get_set_image_ready_status():
            return
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        self._reconcile_openstack_runners(
            runner_scaler,
        )

    def _set_reconcile_timer(self) -> None:
        """Set the timer for regular reconciliation checks."""
        self._event_timer.ensure_event_timer(
            event_name="reconcile-runners",
            interval=int(self.config[RECONCILE_INTERVAL_CONFIG_NAME]),
            timeout=RECONCILIATION_INTERVAL_TIMEOUT_FACTOR
            * int(self.config[RECONCILE_INTERVAL_CONFIG_NAME]),
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
    def _on_upgrade_charm(self, _: UpgradeCharmEvent) -> None:
        """Handle the update of charm."""
        logger.info(UPGRADE_MSG)
        self._common_install_code()

    @catch_charm_errors
    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Handle the configuration change."""
        state = self._setup_state()
        self._set_reconcile_timer()
        self._setup_service(state)

        flush_and_reconcile = False
        if state.charm_config.token != self._stored.token:
            self._stored.token = self.config[TOKEN_CONFIG_NAME]
            flush_and_reconcile = True
        if self.config[PATH_CONFIG_NAME] != self._stored.path:
            self._stored.path = self.config[PATH_CONFIG_NAME]
            flush_and_reconcile = True
        if self.config[LABELS_CONFIG_NAME] != self._stored.labels:
            self._stored.labels = self.config[LABELS_CONFIG_NAME]
            flush_and_reconcile = True

        state = self._setup_state()

        if not self._get_set_image_ready_status():
            return
        if flush_and_reconcile:
            logger.info("Flush and reconcile on config-changed")
            runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
            runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
            self._reconcile_openstack_runners(
                runner_scaler,
            )

    @catch_charm_errors
    def _on_reconcile_runners(self, _: ReconcileRunnersEvent) -> None:
        """Event handler for reconciling runners."""
        self._trigger_reconciliation()

    @catch_charm_errors
    def _on_database_created(self, _: ops.RelationEvent) -> None:
        """Handle the MongoDB database created event."""
        self._trigger_reconciliation()

    @catch_charm_errors
    def _on_endpoints_changed(self, _: ops.RelationEvent) -> None:
        """Handle the MongoDB endpoints changed event."""
        self._trigger_reconciliation()

    def _trigger_reconciliation(self) -> None:
        """Trigger the reconciliation of runners."""
        self.unit.status = MaintenanceStatus("Reconciling runners")
        state = self._setup_state()

        if not self._get_set_image_ready_status():
            return
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        self._reconcile_openstack_runners(
            runner_scaler,
        )

    @catch_action_errors
    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state.

        Args:
            event: The event fired on check_runners action.
        """
        try:
            info = self._manager_client.check_runner()
        except RunnerManagerServiceError as err:
            logger.exception("Failed check runner request")
            event.fail(f"Failed check runner request: {str(err)}")
            return
        event.set_results(info)

    @catch_action_errors
    def _on_reconcile_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of reconcile of runner state.

        Args:
            event: Action event of reconciling the runner.
        """
        self.unit.status = MaintenanceStatus("Reconciling runners")
        state = self._setup_state()

        if not self._get_set_image_ready_status():
            event.fail("Openstack image not yet provided/ready.")
            return
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)

        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            delta = runner_scaler.reconcile()
        except ReconcileError:
            logger.exception(FAILED_TO_RECONCILE_RUNNERS_MSG)
            self.unit.status = ActiveStatus(ACTIVE_STATUS_RECONCILIATION_FAILED_MSG)
            event.fail(FAILED_RECONCILE_ACTION_ERR_MSG)
            return

        self.unit.status = ActiveStatus()
        event.set_results({"delta": {"virtual-machines": delta}})

    @catch_action_errors
    def _on_flush_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of flushing all runner and reconciling afterwards.

        Args:
            event: Action event of flushing all runners.
        """
        state = self._setup_state()

        # Flushing mode not implemented for OpenStack yet.
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        flushed = runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
        logger.info("Flushed %s runners", flushed)
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            delta = runner_scaler.reconcile()
        except ReconcileError:
            logger.exception(FAILED_TO_RECONCILE_RUNNERS_MSG)
            self.unit.status = ActiveStatus(ACTIVE_STATUS_RECONCILIATION_FAILED_MSG)
            event.fail(FAILED_RECONCILE_ACTION_ERR_MSG)
            return
        self.unit.status = ActiveStatus()
        event.set_results({"delta": {"virtual-machines": delta}})

    @catch_charm_errors
    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Handle the update of charm status."""
        self._ensure_reconcile_timer_is_active()
        self._log_juju_processes()

    def _setup_service(self, state: CharmState) -> None:
        """Set up services.

        Args:
            state: The charm state.
        """
        try:
            manager_service.setup(state, self.app.name, self.unit.name)
        except RunnerManagerApplicationError:
            logging.exception("Unable to setup the github-runner-manager service")
            # Not re-raising error for until the github-runner-manager service replaces the
            # library.

    @staticmethod
    def _log_juju_processes() -> None:
        """Log the running Juju processes.

        Log all processes with 'juju' in the command line.
        """
        try:
            processes, _ = execute_command(
                ["ps", "afuwwx"],
                check_exit=True,
            )
            juju_processes = "\n".join(line for line in processes.splitlines() if "juju" in line)
            logger.info("Juju processes: %s", juju_processes)
        except SubprocessError:
            logger.exception("Failed to get Juju processes")

    def _log_charm_status(self) -> None:
        """Log information as a substitute for metrics."""
        juju_charm_path = pathlib.Path(".juju-charm")
        juju_charm = None
        # .juju-charm is not part of the public interface of Juju,
        # and could disappear in a future release.
        try:
            if juju_charm_path.exists():
                juju_charm = juju_charm_path.read_text(encoding="utf-8").strip()
            log = {
                "log_type": "update_state",
                "juju_charm": juju_charm,
                "unit_status": self.unit.status.name,
            }
            logstr = json.dumps(log)
            logger.info(logstr)
        except (AttributeError, TypeError, ValueError):
            logger.exception("Error preparing log metrics")

    @catch_charm_errors
    def _on_stop(self, _: StopEvent) -> None:
        """Handle the stopping of the charm."""
        self._event_timer.disable_event_timer("reconcile-runners")
        state = self._setup_state()
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        runner_scaler.flush(FlushMode.FLUSH_BUSY)

    def _reconcile_openstack_runners(self, runner_scaler: RunnerScaler) -> None:
        """Reconcile the current runners state and intended runner state for OpenStack mode.

        Args:
            runner_scaler: Scaler used to scale the amount of runners.
        """
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            runner_scaler.reconcile()
        except ReconcileError:
            logger.exception(FAILED_TO_RECONCILE_RUNNERS_MSG)
            self.unit.status = ActiveStatus(ACTIVE_STATUS_RECONCILIATION_FAILED_MSG)
        else:
            self.unit.status = ActiveStatus()

    def _install_deps(self) -> None:
        """Install dependences for the charm."""
        logger.info("Installing charm dependencies.")
        self._apt_install(["run-one", "python3-pip"])

    def _apt_install(self, packages: Sequence[str]) -> None:
        """Execute apt install command.

        Args:
            packages: The names of apt packages to install.
        """
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
        self.unit.status = MaintenanceStatus("Added debug-ssh relation")
        state = self._setup_state()

        if not self._get_set_image_ready_status():
            return
        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        runner_scaler.flush()
        self._reconcile_openstack_runners(
            runner_scaler,
        )

    @catch_charm_errors
    def _on_image_relation_joined(self, _: ops.RelationJoinedEvent) -> None:
        """Handle image relation joined event."""
        state = self._setup_state()

        clouds_yaml = state.charm_config.openstack_clouds_yaml
        cloud = list(clouds_yaml["clouds"].keys())[0]
        auth_map = clouds_yaml["clouds"][cloud]["auth"]
        for relation in self.model.relations[IMAGE_INTEGRATION_NAME]:
            relation.data[self.unit].update(auth_map)

    @catch_charm_errors
    def _on_image_relation_changed(self, _: ops.RelationChangedEvent) -> None:
        """Handle image relation changed event."""
        state = self._setup_state()
        self.unit.status = MaintenanceStatus("Update image for runners")

        if not self._get_set_image_ready_status():
            return

        runner_scaler = create_runner_scaler(state, self.app.name, self.unit.name)
        runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
        self._reconcile_openstack_runners(
            runner_scaler,
        )

    def _get_set_image_ready_status(self) -> bool:
        """Check if image is ready for Openstack and charm status accordingly.

        Returns:
            Whether the Openstack image is ready via image integration.
        """
        openstack_image = OpenstackImage.from_charm(self)
        if openstack_image is None:
            self.unit.status = BlockedStatus("Please provide image integration.")
            return False
        if not openstack_image.id:
            self.unit.status = WaitingStatus("Waiting for image over integration.")
            return False
        return True

    @staticmethod
    def _create_labels(state: CharmState) -> list[str]:
        """Create Labels instance.

        Args:
            state: Charm state used to create the labels.

        Returns:
            An instance of Labels.
        """
        image_labels = []
        image = state.runner_config.openstack_image
        if image and image.id and image.tags:
            image_labels = image.tags

        return list(state.charm_config.labels) + image_labels


def _setup_runner_manager_user() -> None:
    """Create the user and required directories for the runner manager."""
    # check if runner_manager user is already existing
    _, retcode = execute_command(["/usr/bin/id", constants.RUNNER_MANAGER_USER], check_exit=False)
    if retcode != 0:
        logger.info("Creating user %s", constants.RUNNER_MANAGER_USER)
        execute_command(
            [
                "/usr/sbin/useradd",
                "--system",
                "--create-home",
                "--user-group",
                constants.RUNNER_MANAGER_USER,
            ],
        )
    execute_command(["/usr/bin/mkdir", "-p", f"/home/{constants.RUNNER_MANAGER_USER}/.ssh"])
    execute_command(
        [
            "/usr/bin/chown",
            "-R",
            f"{constants.RUNNER_MANAGER_USER}:{constants.RUNNER_MANAGER_USER}",
            f"/home/{constants.RUNNER_MANAGER_USER}/.ssh",
        ]
    )
    execute_command(["/usr/bin/chmod", "700", f"/home/{constants.RUNNER_MANAGER_USER}/.ssh"])


if __name__ == "__main__":
    ops.main(GithubRunnerCharm)
