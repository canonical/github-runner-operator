# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import logging
from pathlib import Path

import keystoneauth1.exceptions
import openstack
import openstack.exceptions
import yaml
from openstack.identity.v3.project import Project

from errors import OpenStackInvalidConfigError, OpenStackUnauthorizedError

logger = logging.getLogger(__name__)

CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")


def _validate_cloud_config(cloud_config: dict) -> None:
    """Validate the format of the cloud configuration.

    Args:
        cloud_config: The configuration in clouds.yaml format to validate.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    # dict of format: {clouds: <cloud-name>: <cloud-config>}
    try:
        clouds = list(cloud_config["clouds"].keys())
    except KeyError as exc:
        raise OpenStackInvalidConfigError("Invalid clouds.yaml.") from exc

    if not clouds:
        raise OpenStackInvalidConfigError("No clouds defined in clouds.yaml.")


def _write_config_to_disk(cloud_config: dict) -> None:
    """Write the cloud configuration to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to write to disk.
    """
    CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CLOUDS_YAML_PATH.open("w", encoding="utf-8") as clouds_yaml:
        yaml.dump(cloud_config, clouds_yaml)


def _create_connection(cloud_config) -> openstack.connection.Connection:
    """Create a connection object.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.
    Raises:
        InvalidConfigError: if the config has not all required information.

    Returns:
        An openstack.connection.Connection object.
    """
    clouds = list(cloud_config["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
    cloud_name = clouds[0]

    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. Therefore, no catch here.
    return openstack.connect(cloud_name)


def initialize(cloud_config: dict) -> None:
    """Initialize Openstack integration.

    Validates config and writes it to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    _validate_cloud_config(cloud_config)
    _write_config_to_disk(cloud_config)


def list_projects(cloud_config: dict) -> list[Project]:
    """List all projects in the OpenStack cloud.

    The purpose of the method is just to try out openstack integration and
    it may be removed in the future.

    It currently returns objects directly from the sdk,
    which may not be ideal (mapping to domain objects may be preferable).

    Returns:
        A list of projects.
    """
    conn = _create_connection(cloud_config)
    try:
        projects = conn.list_projects()
        logger.debug("OpenStack connection successful.")
        logger.debug("Projects: %s", projects)
        # pylint thinks this isn't an exception
    except keystoneauth1.exceptions.http.Unauthorized as exc:
        raise OpenStackUnauthorizedError(  # pylint: disable=bad-exception-cause
            "Unauthorized to connect to OpenStack."
        ) from exc

    return projects
