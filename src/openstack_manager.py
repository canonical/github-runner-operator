# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for handling interactions with OpenStack."""
import logging
from pathlib import Path

import keystoneauth1.exceptions
import openstack
import yaml

logger = logging.getLogger(__name__)

CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")


class InvalidConfigError(Exception):
    """Represents an invalid OpenStack configuration.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the InvalidConfigError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


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


def _connect(cloud_config):
    clouds = list(cloud_config["clouds"].keys())
    if len(clouds) > 1:
        logger.warning("Multiple clouds defined in clouds.yaml. Using the first one to connect.")
    cloud_name = clouds[0]
    try:
        openstack.connect(cloud_name)
        logger.debug("OpenStack connection successful.")
    # pylint thinks this isn't an exception
    except keystoneauth1.exceptions.MissingRequiredOptions as exc:
        raise InvalidConfigError(  # pylint: disable=bad-exception-cause
            "Missing required Openstack credentials"
        ) from exc


def initialize_openstack(cloud_config: dict) -> None:
    """Write config to disk and check connection.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.

    Raises:
        InvalidConfigError: if the format of the config is invalid.
    """
    _validate_cloud_config(cloud_config)
    _write_config_to_disk(cloud_config)
    _connect(cloud_config)
