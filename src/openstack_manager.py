# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import logging
from pathlib import Path

import keystoneauth1.exceptions
import openstack
import openstack.exceptions
import yaml

logger = logging.getLogger(__name__)

CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")


class OpenStackError(Exception):
    """Base class for OpenStack errors."""


class InvalidConfigError(OpenStackError):
    """Represents an invalid OpenStack configuration."""


class UnauthorizedError(OpenStackError):
    """Represents an unauthorized connection to OpenStack."""


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
        raise InvalidConfigError("Invalid clouds.yaml.") from exc

    if not clouds:
        raise InvalidConfigError("No clouds defined in clouds.yaml.")


def _write_config_to_disk(cloud_config: dict):
    CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CLOUDS_YAML_PATH.open("w", encoding="utf-8") as clouds_yaml:
        yaml.dump(cloud_config, clouds_yaml)


def _create_connection(cloud_config):
    """Create a connection object.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.
    Raises:
        InvalidConfigError: if the config has not all required information.
    """
    clouds = list(cloud_config["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
    cloud_name = clouds[0]

    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. I will leave it here for now.
    return openstack.connect(cloud_name)


def initialize(cloud_config: dict) -> None:
    """Validate config and write to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    _validate_cloud_config(cloud_config)
    _write_config_to_disk(cloud_config)


def list_projects(cloud_config: dict):
    """List all servers in the OpenStack cloud.

    The purpose of the method is just to try out openstack integration and
    it may be removed in the future.

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
        raise UnauthorizedError(  # pylint: disable=bad-exception-cause
            "Unauthorized to connect to OpenStack."
        ) from exc

    return projects
