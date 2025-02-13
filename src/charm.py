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
import logging
from typing import Any, Callable, Sequence, TypeVar

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    Image,
    NonReactiveCombination,
    NonReactiveConfiguration,
    ReactiveConfiguration,
    SupportServiceConfig,
)
from github_runner_manager.configuration.github import GitHubConfiguration, GitHubPath
from github_runner_manager.errors import ReconcileError
from github_runner_manager.manager.cloud_runner_manager import (
    GitHubRunnerConfig,
)
from github_runner_manager.manager.runner_manager import (
    FlushMode,
    RunnerManager,
    RunnerManagerConfig,
)
from github_runner_manager.manager.runner_scaler import RunnerScaler
from github_runner_manager.openstack_cloud.configuration import (
    OpenStackConfiguration,
    OpenStackCredentials,
)
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
    OpenStackServerConfig,
)
from github_runner_manager.reactive.types_ import QueueConfig
from github_runner_manager.reactive.types_ import RunnerConfig as ReactiveRunnerConfig
from github_runner_manager.types_ import SystemUserConfig
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
    SubprocessError,
    TokenError,
)
from event_timer import EventTimer, TimerStatusError

# We assume a stuck reconcile event when it takes longer
# than 10 times a normal interval. Currently, we are only aware of
# https://bugs.launchpad.net/juju/+bug/2055184 causing a stuck reconcile event.
RECONCILIATION_INTERVAL_TIMEOUT_FACTOR = 10
RECONCILE_RUNNERS_EVENT = "reconcile-runners"

# This is currently hardcoded and may be moved to a config option in the future.
REACTIVE_MQ_DB_NAME = "github-runner-webhook-router"


GITHUB_SELF_HOSTED_ARCH_LABELS = {"x64", "arm64"}

ROOT_USER = "root"
RUNNER_MANAGER_USER = "runner-manager"
RUNNER_MANAGER_GROUP = "runner-manager"

ACTIVE_STATUS_RECONCILIATION_FAILED_MSG = "Last reconciliation failed."
FAILED_TO_RECONCILE_RUNNERS_MSG = "Failed to reconcile runners"
FAILED_RECONCILE_ACTION_ERR_MSG = (
    "Failed to reconcile runners. Look at the juju logs for more information."
)


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
        self.framework.observe(
            self.on.update_dependencies_action, self._on_update_dependencies_action
        )
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.database = DatabaseRequires(
            self, relation_name="mongodb", database_name=REACTIVE_MQ_DB_NAME
        )
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)

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
        runner_scaler = self._get_runner_scaler(state)
        self._reconcile_openstack_runners(
            runner_scaler,
            base_num=state.runner_config.base_virtual_machines,
            max_num=state.runner_config.max_total_virtual_machines,
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

    @catch_charm_errors
    def _on_upgrade_charm(self, _: UpgradeCharmEvent) -> None:
        """Handle the update of charm."""
        logger.info("Reinstalling dependencies...")
        self._common_install_code()

    @catch_charm_errors
    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Handle the configuration change."""
        state = self._setup_state()
        self._set_reconcile_timer()

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
            runner_scaler = self._get_runner_scaler(state)
            runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
            self._reconcile_openstack_runners(
                runner_scaler,
                base_num=state.runner_config.base_virtual_machines,
                max_num=state.runner_config.max_total_virtual_machines,
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
        runner_scaler = self._get_runner_scaler(state)
        self._reconcile_openstack_runners(
            runner_scaler,
            base_num=state.runner_config.base_virtual_machines,
            max_num=state.runner_config.max_total_virtual_machines,
        )

    @catch_action_errors
    def _on_check_runners_action(self, event: ActionEvent) -> None:
        """Handle the action of checking of runner state.

        Args:
            event: The event fired on check_runners action.
        """
        state = self._setup_state()

        runner_scaler = self._get_runner_scaler(state)
        info = runner_scaler.get_runner_info()
        event.set_results(
            {
                "online": info.online,
                "busy": info.busy,
                "offline": info.offline,
                "unknown": info.unknown,
                "runners": info.runners,
                "busy-runners": info.busy_runners,
            }
        )

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
        runner_scaler = self._get_runner_scaler(state)

        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            delta = runner_scaler.reconcile(
                base_quantity=state.runner_config.base_virtual_machines,
                max_quantity=state.runner_config.max_total_virtual_machines,
            )
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
        runner_scaler = self._get_runner_scaler(state)
        flushed = runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
        logger.info("Flushed %s runners", flushed)
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            delta = runner_scaler.reconcile(
                state.runner_config.base_virtual_machines,
                state.runner_config.max_total_virtual_machines,
            )
        except ReconcileError:
            logger.exception(FAILED_TO_RECONCILE_RUNNERS_MSG)
            self.unit.status = ActiveStatus(ACTIVE_STATUS_RECONCILIATION_FAILED_MSG)
            event.fail(FAILED_RECONCILE_ACTION_ERR_MSG)
            return
        self.unit.status = ActiveStatus()
        event.set_results({"delta": {"virtual-machines": delta}})

    @catch_action_errors
    def _on_update_dependencies_action(self, event: ActionEvent) -> None:
        """Handle the action of updating dependencies and flushing runners if needed.

        Args:
            event: Action event of updating dependencies.
        """
        # No dependencies managed by the charm for OpenStack-based runners.
        event.set_results({"flush": False})

    @catch_charm_errors
    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Handle the update of charm status."""
        self._ensure_reconcile_timer_is_active()
        self._log_juju_processes()

    @catch_charm_errors
    def _on_stop(self, _: StopEvent) -> None:
        """Handle the stopping of the charm."""
        self._event_timer.disable_event_timer("reconcile-runners")
        state = self._setup_state()
        runner_scaler = self._get_runner_scaler(state)
        runner_scaler.flush(FlushMode.FLUSH_BUSY)

    def _reconcile_openstack_runners(
        self, runner_scaler: RunnerScaler, base_num: int, max_num: int
    ) -> None:
        """Reconcile the current runners state and intended runner state for OpenStack mode.

        Args:
            runner_scaler: Scaler used to scale the amount of runners.
            base_num: Target number of runners.
            max_num: Target number of runners.
        """
        self.unit.status = MaintenanceStatus("Reconciling runners")
        try:
            runner_scaler.reconcile(base_quantity=base_num, max_quantity=max_num)
        except ReconcileError:
            logger.exception(FAILED_TO_RECONCILE_RUNNERS_MSG)
            self.unit.status = ActiveStatus(ACTIVE_STATUS_RECONCILIATION_FAILED_MSG)
        else:
            self.unit.status = ActiveStatus()

    def _install_deps(self) -> None:
        """Install dependences for the charm."""
        logger.info("Installing charm dependencies.")
        self._apt_install(["run-one"])

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
        runner_scaler = self._get_runner_scaler(state)
        runner_scaler.flush()
        self._reconcile_openstack_runners(
            runner_scaler,
            base_num=state.runner_config.base_virtual_machines,
            max_num=state.runner_config.max_total_virtual_machines,
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

        runner_scaler = self._get_runner_scaler(state)
        runner_scaler.flush(flush_mode=FlushMode.FLUSH_IDLE)
        self._reconcile_openstack_runners(
            runner_scaler,
            base_num=state.runner_config.base_virtual_machines,
            max_num=state.runner_config.max_total_virtual_machines,
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

    def _get_application_configuration(self, state: CharmState) -> ApplicationConfiguration:
        """TODO."""
        extra_labels = list(state.charm_config.labels)
        github_configuration = GitHubConfiguration(
            token=state.charm_config.token,
            path=state.charm_config.path,
        )
        service_config = SupportServiceConfig(
            proxy_config=state.proxy_config,
            dockerhub_mirror=state.charm_config.dockerhub_mirror,
            ssh_debug_connections=state.ssh_debug_connections,
            repo_policy_compliance=state.charm_config.repo_policy_compliance,
        )
        openstack_image = state.runner_config.openstack_image
        image_labels = []
        if openstack_image and openstack_image.id and openstack_image.tags:
            image_labels = openstack_image.tags
        image = Image(
            image=openstack_image.id,
            labels=image_labels,
        )
        flavor = Flavor(
            name=state.runner_config.flavor_label_combinations[0].flavor,
            labels=(
                []
                if not state.runner_config.flavor_label_combinations[0].label
                else [state.runner_config.flavor_label_combinations[0].label]
            ),
        )
        non_reactive_configuration = NonReactiveConfiguration(
            combinations=[
                NonReactiveCombination(
                    image=Image,
                    flavor=Flavor,
                    base_virtual_machines=state.runner_config.base_virtual_machines,
                )
            ]
        )
        if reactive_config := state.reactive_config:
            reactive_configuration = ReactiveConfiguration(
                queue=QueueConfig(mongodb_uri=reactive_config.mq_uri, queue_name=self.app.name),
                max_total_virtual_machines=state.runner_config.max_total_virtual_machines,
                images=[image],
                flavors=[flavor],
            )
        else:
            reactive_configuration = None

        return ApplicationConfiguration(
            extra_labels=extra_labels,
            github_config=github_configuration,
            service_config=service_config,
            non_reactive_configuration=non_reactive_configuration,
            reactive_configuration=reactive_configuration,
        )

    def _get_openstack_configuration(self, state: CharmState) -> OpenStackConfiguration:
        """TODO."""
        clouds = list(state.charm_config.openstack_clouds_yaml["clouds"].keys())
        if len(clouds) > 1:
            logger.warning(
                "Multiple clouds defined in clouds.yaml. Using the first one to connect."
            )
        first_cloud_config = state.charm_config.openstack_clouds_yaml["clouds"][clouds[0]]
        credentials = OpenStackCredentials(
            auth_url=first_cloud_config["auth"]["auth_url"],
            project_name=first_cloud_config["auth"]["project_name"],
            username=first_cloud_config["auth"]["username"],
            password=first_cloud_config["auth"]["password"],
            user_domain_name=first_cloud_config["auth"]["user_domain_name"],
            project_domain_name=first_cloud_config["auth"]["project_domain_name"],
            region_name=first_cloud_config["region_name"],
        )
        return OpenStackConfiguration(
            vm_prefix=self.unit.name.replace("/", "-"),
            network=state.runner_config.openstack_network,
            credentials=credentials,
        )

    def _get_runner_scaler(self, state: CharmState) -> RunnerScaler:
        """Get runner scaler instance for scaling runners.

        Args:
            state: Charm state.

        Returns:
            An instance of RunnerScaler.
        """
        token = state.charm_config.token
        path = state.charm_config.path

        openstack_runner_manager_config = self._create_openstack_runner_manager_config(path, state)
        openstack_runner_manager = OpenStackRunnerManager(
            config=openstack_runner_manager_config,
        )
        runner_manager_config = RunnerManagerConfig(
            name=self.app.name,
            token=token,
            path=path,
        )
        runner_manager = RunnerManager(
            cloud_runner_manager=openstack_runner_manager,
            config=runner_manager_config,
        )
        reactive_runner_config = None
        if reactive_config := state.reactive_config:
            # The charm is not able to determine which architecture the runner is running on,
            # so we add all architectures to the supported labels.
            supported_labels = set(self._create_labels(state)) | GITHUB_SELF_HOSTED_ARCH_LABELS
            reactive_runner_config = ReactiveRunnerConfig(
                queue=QueueConfig(mongodb_uri=reactive_config.mq_uri, queue_name=self.app.name),
                runner_manager=runner_manager_config,
                cloud_runner_manager=openstack_runner_manager_config,
                github_token=token,
                supported_labels=supported_labels,
                system_user=SystemUserConfig(user=RUNNER_MANAGER_USER, group=RUNNER_MANAGER_GROUP),
            )
        return RunnerScaler(
            runner_manager=runner_manager, reactive_runner_config=reactive_runner_config
        )

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

    def _create_openstack_runner_manager_config(
        self, path: GitHubPath, state: CharmState
    ) -> OpenStackRunnerManagerConfig:
        """Create OpenStackRunnerManagerConfig instance.

        Args:
            path: GitHub repository path in the format '<org>/<repo>', or the GitHub organization
                name.
            state: Charm state.

        Returns:
            An instance of OpenStackRunnerManagerConfig.
        """
        clouds = list(state.charm_config.openstack_clouds_yaml["clouds"].keys())
        if len(clouds) > 1:
            logger.warning(
                "Multiple clouds defined in clouds.yaml. Using the first one to connect."
            )
        first_cloud_config = state.charm_config.openstack_clouds_yaml["clouds"][clouds[0]]
        credentials = OpenStackCredentials(
            auth_url=first_cloud_config["auth"]["auth_url"],
            project_name=first_cloud_config["auth"]["project_name"],
            username=first_cloud_config["auth"]["username"],
            password=first_cloud_config["auth"]["password"],
            user_domain_name=first_cloud_config["auth"]["user_domain_name"],
            project_domain_name=first_cloud_config["auth"]["project_domain_name"],
            region_name=first_cloud_config["region_name"],
        )
        server_config = None
        image = state.runner_config.openstack_image
        if image and image.id:
            server_config = OpenStackServerConfig(
                image=image.id,
                # Pending to add support for more flavor label combinations
                flavor=state.runner_config.flavor_label_combinations[0].flavor,
                network=state.runner_config.openstack_network,
            )
        labels = self._create_labels(state)
        runner_config = GitHubRunnerConfig(github_path=path, labels=labels)
        service_config = SupportServiceConfig(
            proxy_config=state.proxy_config,
            dockerhub_mirror=state.charm_config.dockerhub_mirror,
            ssh_debug_connections=state.ssh_debug_connections,
            repo_policy_compliance=state.charm_config.repo_policy_compliance,
        )
        openstack_runner_manager_config = OpenStackRunnerManagerConfig(
            name=self.app.name,
            # The prefix is set to f"{application_name}-{unit number}"
            prefix=self.unit.name.replace("/", "-"),
            credentials=credentials,
            server_config=server_config,
            runner_config=runner_config,
            service_config=service_config,
            system_user_config=SystemUserConfig(
                user=RUNNER_MANAGER_USER, group=RUNNER_MANAGER_GROUP
            ),
        )
        return openstack_runner_manager_config


def _setup_runner_manager_user() -> None:
    """Create the user and required directories for the runner manager."""
    # check if runner_manager user is already existing
    _, retcode = execute_command(["/usr/bin/id", RUNNER_MANAGER_USER], check_exit=False)
    if retcode != 0:
        logger.info("Creating user %s", RUNNER_MANAGER_USER)
        execute_command(
            [
                "/usr/sbin/useradd",
                "--system",
                "--create-home",
                "--user-group",
                RUNNER_MANAGER_USER,
            ],
        )
    execute_command(["/usr/bin/mkdir", "-p", f"/home/{RUNNER_MANAGER_USER}/.ssh"])
    execute_command(
        [
            "/usr/bin/chown",
            "-R",
            f"{RUNNER_MANAGER_USER}:{RUNNER_MANAGER_USER}",
            f"/home/{RUNNER_MANAGER_USER}/.ssh",
        ]
    )
    execute_command(["/usr/bin/chmod", "700", f"/home/{RUNNER_MANAGER_USER}/.ssh"])


if __name__ == "__main__":
    ops.main(GithubRunnerCharm)
