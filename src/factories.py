# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for creating configuration classes for the github-runner-operator library."""

import logging

from github_runner_manager.configuration import (
    ApplicationConfiguration,
    Flavor,
    Image,
    NonReactiveCombination,
    NonReactiveConfiguration,
    QueueConfig,
    ReactiveConfiguration,
    SupportServiceConfig,
)
from github_runner_manager.configuration.github import GitHubConfiguration
from github_runner_manager.manager.cloud_runner_manager import (
    GitHubRunnerConfig,
)
from github_runner_manager.manager.runner_manager import (
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
from github_runner_manager.reactive.types_ import ReactiveProcessConfig

from charm_state import CharmState

GITHUB_SELF_HOSTED_ARCH_LABELS = {"x64", "arm64"}

logger = logging.getLogger(__name__)


def create_application_configuration(state: CharmState, app_name: str) -> ApplicationConfiguration:
    """TODO.

    Args:
        state: TODO
        app_name: TODO

    Returns:
        TODO
    """
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
        images = [image]
        flavors = [flavor]
    else:
        combinations = []
        images = []
        flavors = []
    non_reactive_configuration = NonReactiveConfiguration(combinations=combinations)

    reactive_configuration = None
    if reactive_config := state.reactive_config:
        reactive_configuration = ReactiveConfiguration(
            queue=QueueConfig(mongodb_uri=reactive_config.mq_uri, queue_name=app_name),
            max_total_virtual_machines=state.runner_config.max_total_virtual_machines,
            images=images,
            flavors=flavors,
        )
    return ApplicationConfiguration(
        name=app_name,
        extra_labels=extra_labels,
        github_config=github_configuration,
        service_config=service_config,
        non_reactive_configuration=non_reactive_configuration,
        reactive_configuration=reactive_configuration,
    )


def create_openstack_configuration(state: CharmState, unit_name: str) -> OpenStackConfiguration:
    """TODO.

    Args:
        state: TODO
        unit_name: TODO

    Returns:
        TODO
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


# This function will disappear in the next PR.
def create_runner_scaler(  # pylint: disable=too-many-locals
    state: CharmState, app_name: str, unit_name: str
) -> RunnerScaler:
    """Get runner scaler instance for scaling runners.

    Args:
        state: Charm state.
        app_name: TODO.
        unit_name: TODO.

    Returns:
        An instance of RunnerScaler.
    """
    openstack_configuration = create_openstack_configuration(state, unit_name)
    application_configuration = create_application_configuration(state, app_name)

    labels = application_configuration.extra_labels
    server_config = None
    if combinations := application_configuration.non_reactive_configuration.combinations:
        combination = combinations[0]
        if combination.image.labels:
            labels += combination.image.labels
        if combination.flavor.labels:
            labels += combination.flavor.labels

        server_config = OpenStackServerConfig(
            image=combination.image.name,
            # Pending to add support for more flavor label combinations
            flavor=combination.flavor.name,
            network=openstack_configuration.network,
        )

    runner_config = GitHubRunnerConfig(
        github_path=application_configuration.github_config.path, labels=labels
    )
    openstack_runner_manager_config = OpenStackRunnerManagerConfig(
        # The prefix is set to f"{application_name}-{unit number}"
        prefix=openstack_configuration.vm_prefix,
        credentials=openstack_configuration.credentials,
        server_config=server_config,
        runner_config=runner_config,
        service_config=application_configuration.service_config,
    )

    openstack_runner_manager = OpenStackRunnerManager(
        config=openstack_runner_manager_config,
    )
    runner_manager_config = RunnerManagerConfig(
        name=application_configuration.name,
        github_configuration=application_configuration.github_config,
    )
    runner_manager = RunnerManager(
        cloud_runner_manager=openstack_runner_manager,
        config=runner_manager_config,
    )
    reactive_runner_config = None
    if reactive_config := application_configuration.reactive_configuration:
        # The charm is not able to determine which architecture the runner is running on,
        # so we add all architectures to the supported labels.
        supported_labels = set(labels) | GITHUB_SELF_HOSTED_ARCH_LABELS
        reactive_runner_config = ReactiveProcessConfig(
            queue=reactive_config.queue,
            runner_manager=runner_manager_config,
            cloud_runner_manager=openstack_runner_manager_config,
            github_token=application_configuration.github_config.token,
            supported_labels=supported_labels,
        )
    return RunnerScaler(
        runner_manager=runner_manager, reactive_process_config=reactive_runner_config
    )
