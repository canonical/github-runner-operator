# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for creating configuration classes for the github-runner-operator library."""

import logging

from github_runner_manager import constants
from github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    Image,
    NonReactiveCombination,
    NonReactiveConfiguration,
    QueueConfig,
    ReactiveConfiguration,
    SupportServiceConfig,
    UserInfo,
)
from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.manager.runner_scaler import RunnerScaler
from github_runner_manager.openstack_cloud.configuration import (
    OpenStackConfiguration,
    OpenStackCredentials,
)

from charm_state import CharmState

logger = logging.getLogger(__name__)


def create_runner_scaler(state: CharmState, app_name: str, unit_name: str) -> RunnerScaler:
    """Get runner scaler instance for scaling runners.

    Args:
        state: The CharmState.
        app_name: Name of the application.
        unit_name: Unit name for the prefix for instances.

    Returns:
        An instance of RunnerScaler.
    """
    application_configuration = create_application_configuration(state, app_name, unit_name)
    user = UserInfo(constants.RUNNER_MANAGER_USER, constants.RUNNER_MANAGER_GROUP)

    return RunnerScaler.build(
        application_configuration=application_configuration,
        user=user,
    )


def create_application_configuration(
    state: CharmState, app_name: str, unit_name: str
) -> ApplicationConfiguration:
    """Create the ApplicationConfiguration from the CharmState.

    Args:
        state: The CharmState.
        app_name: Application name to pass to ApplicationConfiguration.
        unit_name: The unit name of the juju unit.

    Returns:
        The created ApplicationConfiguration
    """
    extra_labels = list(state.charm_config.labels)
    github_configuration = GitHubConfiguration(
        token=state.charm_config.token,
        path=state.charm_config.path,
    )
    service_config = SupportServiceConfig(
        manager_proxy_command=state.charm_config.manager_proxy_command,
        proxy_config=state.proxy_config,
        runner_proxy_config=state.runner_proxy_config,
        dockerhub_mirror=state.charm_config.dockerhub_mirror,
        ssh_debug_connections=state.ssh_debug_connections,
        repo_policy_compliance=state.charm_config.repo_policy_compliance,
        use_aproxy=state.charm_config.use_aproxy,
    )
    non_reactive_configuration = _get_non_reactive_configuration(state)
    reactive_configuration = _get_reactive_configuration(state, app_name)
    openstack_configuration = create_openstack_configuration(state, unit_name)
    return ApplicationConfiguration(
        name=app_name,
        extra_labels=extra_labels,
        github_config=github_configuration,
        service_config=service_config,
        non_reactive_configuration=non_reactive_configuration,
        reactive_configuration=reactive_configuration,
        openstack_configuration=openstack_configuration,
    )


def _get_non_reactive_configuration(state: CharmState) -> NonReactiveConfiguration:
    """Get NonReactiveConfiguration from CharmState.

    Currently only one image and one flavor is supported.
    """
    openstack_image = state.runner_config.openstack_image
    image_labels = []
    combinations = []
    if openstack_image and openstack_image.id:
        if openstack_image.tags:
            image_labels = openstack_image.tags
        image = Image(
            name=openstack_image.id,
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
        combinations = [
            NonReactiveCombination(
                image=image,
                flavor=flavor,
                base_virtual_machines=state.runner_config.base_virtual_machines,
            )
        ]
    return NonReactiveConfiguration(combinations=combinations)


def _get_reactive_configuration(state: CharmState, app_name: str) -> ReactiveConfiguration:
    """Get ReactiveConfiguration from CharmState and app_name.

    Currently only one image and one flavor is supported.
    """
    if not state.reactive_config:
        return None
    reactive_config = state.reactive_config
    openstack_image = state.runner_config.openstack_image
    image_labels = []
    images = []
    flavors = []
    if openstack_image and openstack_image.id:
        if openstack_image.tags:
            image_labels = openstack_image.tags
        image = Image(
            name=openstack_image.id,
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
        images = [image]
        flavors = [flavor]
    return ReactiveConfiguration(
        queue=QueueConfig(mongodb_uri=reactive_config.mq_uri, queue_name=app_name),
        max_total_virtual_machines=state.runner_config.max_total_virtual_machines,
        images=images,
        flavors=flavors,
    )


def create_openstack_configuration(state: CharmState, unit_name: str) -> OpenStackConfiguration:
    """Create the OpenStack configuration.

    Args:
        state: The CharmState.
        unit_name: To set a prefix for the instances to create.

    Returns:
        The OpenStackConfiguration.
    """
    clouds = list(state.charm_config.openstack_clouds_yaml["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
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
        vm_prefix=unit_name.replace("/", "-"),
        network=state.runner_config.openstack_network,
        credentials=credentials,
    )
