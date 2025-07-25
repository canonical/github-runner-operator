#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for creating and managing GitHub self-hosted runner instances."""

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
import shutil
from typing import Any, Callable, Sequence, TypeVar

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from charms.operator_libs_linux.v1 import systemd
from github_runner_manager import constants
from github_runner_manager.metrics.events import METRICS_LOG_PATH
from github_runner_manager.platform.platform_provider import TokenError
from github_runner_manager.utilities import set_env_var
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
    MONGO_DB_INTEGRATION_NAME,
    PATH_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    CharmConfigInvalidError,
    CharmState,
    OpenstackImage,
    build_proxy_config_from_charm,
)
from errors import (
    ConfigurationError,
    ImageIntegrationMissingError,
    ImageNotFoundError,
    LogrotateSetupError,
    MissingMongoDBError,
    RunnerManagerApplicationError,
    RunnerManagerApplicationInstallError,
    RunnerManagerServiceError,
    SubprocessError,
)
from manager_client import GitHubRunnerManagerClient

# This is currently hardcoded and may be moved to a config option in the future.
REACTIVE_MQ_DB_NAME = "github-runner-webhook-router"


ACTIVE_STATUS_RECONCILIATION_FAILED_MSG = "Last reconciliation failed."
FAILED_TO_RECONCILE_RUNNERS_MSG = "Failed to reconcile runners"
FAILED_RECONCILE_ACTION_ERR_MSG = (
    "Failed to reconcile runners. Look at the juju logs for more information."
)
UPGRADE_MSG = "Upgrading github-runner charm."
LEGACY_RECONCILE_TIMER_SERVICE = "ghro.reconcile-runners.timer"
LEGACY_RECONCILE_SERVICE = "ghro.reconcile-runners.service"


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
        except ImageIntegrationMissingError:
            logger.exception("Missing image integration.")
            self.unit.status = BlockedStatus("Please provide image integration.")
            manager_service.stop()
        except ImageNotFoundError:
            logger.exception("Missing image in image integration.")
            self.unit.status = WaitingStatus("Waiting for image over integration.")
            manager_service.stop()

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
        except RunnerManagerServiceError as err:
            logger.exception("Failed runner manager request")
            event.fail(f"Failed runner manager request: {str(err)}")

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

        self._grafana_agent = COSAgentProvider(
            self,
            metrics_endpoints=[
                {"path": "/metrics", "port": int(manager_service.GITHUB_RUNNER_MANAGER_PORT)}
            ],
        )

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
        self.framework.observe(self.on.check_runners_action, self._on_check_runners_action)
        self.framework.observe(self.on.flush_runners_action, self._on_flush_runners_action)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.database = DatabaseRequires(
            self, relation_name="mongodb", database_name=REACTIVE_MQ_DB_NAME
        )
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)
        self.framework.observe(
            self.on[MONGO_DB_INTEGRATION_NAME].relation_broken, self._on_mongodb_relation_broken
        )

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

    def _set_proxy_env_var(self) -> None:
        """Set the HTTP proxy environment variables."""
        proxy_config = build_proxy_config_from_charm()

        if proxy_config.no_proxy is not None:
            set_env_var("NO_PROXY", proxy_config.no_proxy)
            set_env_var("no_proxy", proxy_config.no_proxy)
        if proxy_config.http is not None:
            set_env_var("HTTP_PROXY", proxy_config.http)
            set_env_var("http_proxy", proxy_config.http)
        if proxy_config.https is not None:
            set_env_var("HTTPS_PROXY", proxy_config.https)
            set_env_var("https_proxy", proxy_config.https)

    def _common_install_code(self) -> bool:
        """Installation code shared between install and upgrade hook.

        Raises:
            LogrotateSetupError: Failed to setup logrotate.
            SubprocessError: Failed to install dependencies.

        Returns:
            True if installation was successful, False otherwise.
        """
        self._set_proxy_env_var()

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
        self._check_image_ready()
        self.unit.status = ActiveStatus()

    @catch_charm_errors
    def _on_upgrade_charm(self, _: UpgradeCharmEvent) -> None:
        """Handle the update of charm."""
        logger.info(UPGRADE_MSG)
        self._common_install_code()
        _disable_legacy_service()
        state = self._setup_state()
        self._setup_service(state)
        self._manager_client.flush_runner()

    @catch_charm_errors
    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Handle the configuration change."""
        state = self._setup_state()

        flush_runners = False
        if self.config[TOKEN_CONFIG_NAME] != self._stored.token:
            self._stored.token = self.config[TOKEN_CONFIG_NAME]
            flush_runners = True
        if self.config[PATH_CONFIG_NAME] != self._stored.path:
            self._stored.path = self.config[PATH_CONFIG_NAME]
            flush_runners = True
        if self.config[LABELS_CONFIG_NAME] != self._stored.labels:
            self._stored.labels = self.config[LABELS_CONFIG_NAME]
            flush_runners = True

        self._check_image_ready()

        self._setup_service(state)

        if flush_runners:
            logger.info("Flush runners on config-changed")
            self._manager_client.flush_runner()
        self.unit.status = ActiveStatus()

    @catch_action_errors
    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state.

        Args:
            event: The event fired on check_runners action.
        """
        info = self._manager_client.check_runner()
        event.set_results(info)

    @catch_action_errors
    def _on_flush_runners_action(self, _: ActionEvent) -> None:
        """Handle the action of flushing all runner and reconciling afterwards."""
        self._manager_client.flush_runner()

    @catch_charm_errors
    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Handle the update of charm status."""
        self._log_juju_processes()

    def _setup_service(self, state: CharmState) -> None:
        """Set up services.

        Args:
            state: The charm state.

        Raises:
            RunnerManagerApplicationError: The runner manager service is not ready for requests or
                has errors.
        """
        try:
            manager_service.setup(state, self.app.name, self.unit.name)
        except RunnerManagerApplicationError:
            logging.exception("Unable to setup the github-runner-manager service")
            raise
        self._manager_client.wait_till_ready()

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
        self._manager_client.flush_runner(busy=True)
        manager_service.stop()

    def _install_deps(self) -> None:
        """Install dependences for the charm."""
        logger.info("Installing charm dependencies.")
        self._apt_install(["run-one", "python3-pip", "python3-venv"])

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
        self._check_image_ready()

        state = self._setup_state()
        self._setup_service(state)

        self._manager_client.flush_runner()
        self.unit.status = ActiveStatus()

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
        self.unit.status = MaintenanceStatus("Update image for runners")
        self._check_image_ready()

        state = self._setup_state()
        self._setup_service(state)

        self._manager_client.flush_runner()
        self.unit.status = ActiveStatus()

    @catch_charm_errors
    def _on_database_created(self, _: ops.RelationEvent) -> None:
        """Handle the MongoDB database created event."""
        state = self._setup_state()
        self._setup_service(state)

    @catch_charm_errors
    def _on_endpoints_changed(self, _: ops.RelationEvent) -> None:
        """Handle the MongoDB endpoints changed event."""
        state = self._setup_state()
        self._setup_service(state)

    @catch_charm_errors
    def _on_mongodb_relation_broken(self, _: ops.RelationDepartedEvent) -> None:
        """Handle the MongoDB relation broken event."""
        state = self._setup_state()
        self._setup_service(state)

    def _check_image_ready(self) -> None:
        """Check if image is ready raises error if not.

        Raises:
            ImageIntegrationMissingError: No image integration found.
            ImageNotFoundError: No image found in the image integration.
        """
        openstack_image = OpenstackImage.from_charm(self)
        if openstack_image is None:
            raise ImageIntegrationMissingError("No image integration found")
        if not openstack_image.id:
            raise ImageNotFoundError("No image found in the image integration")

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
    # Give the user access to write to /var/log
    execute_command(["/usr/sbin/usermod", "-a", "-G", "syslog", constants.RUNNER_MANAGER_USER])
    execute_command(["/usr/bin/chmod", "g+w", "/var/log"])

    # For charm upgrade, previous revision root owns the metric logs, this is changed to runner
    # manager.
    if METRICS_LOG_PATH.exists():
        shutil.chown(
            METRICS_LOG_PATH,
            user=constants.RUNNER_MANAGER_USER,
            group=constants.RUNNER_MANAGER_GROUP,
        )


def _disable_legacy_service() -> None:
    """Disable any legacy service."""
    logger.info("Attempting to stop legacy services")
    try:
        systemd.service_disable(LEGACY_RECONCILE_TIMER_SERVICE)
        systemd.service_stop(LEGACY_RECONCILE_TIMER_SERVICE)
    except systemd.SystemdError:
        pass
    try:
        systemd.service_disable(LEGACY_RECONCILE_SERVICE)
        systemd.service_stop(LEGACY_RECONCILE_SERVICE)
    except systemd.SystemdError:
        pass

    try:
        timer_path = pathlib.Path("/etc/systemd/system") / LEGACY_RECONCILE_TIMER_SERVICE
        service_path = pathlib.Path("/etc/systemd/system") / LEGACY_RECONCILE_SERVICE
        timer_path.unlink(missing_ok=True)
        service_path.unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Unexpected exception during removal of legacy systemd service files", exc_info=True
        )

    try:
        systemd.daemon_reload()
    except systemd.SystemdError:
        logger.warning("Unable to reload systemd daemon", exc_info=True)


if __name__ == "__main__":
    ops.main(GithubRunnerCharm)
