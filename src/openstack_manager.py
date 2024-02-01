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


def initialize_openstack(clouds_yaml: str) -> None:
    """Initialize clouds.yaml and check connection.

    Args:
        clouds_yaml: The clouds.yaml configuration to apply.

    Raises:
        InvalidConfigError: if an invalid clouds_yaml configuration was passed.
    """
    # dict of format: {clouds: <cloud-name>: <cloud-config>}
    cloud_config: dict = yaml.safe_load(clouds_yaml)
    try:
        cloud_name = list(cloud_config["clouds"].keys())[0]
    except (KeyError, IndexError) as exc:
        raise InvalidConfigError("Invalid clouds.yaml.") from exc
    CLOUDS_YAML_PATH.write_text(clouds_yaml, encoding="utf-8")
    try:
        openstack.connect(cloud_name)
    # pylint thinks this isn't an exception
    except keystoneauth1.exceptions.MissingRequiredOptions as exc:
        raise InvalidConfigError(  # pylint: disable=bad-exception-cause
            "Missing required Openstack credentials"
        ) from exc
