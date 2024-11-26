# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing Openstack cloud."""

import logging
from typing import TypedDict, cast

from github_runner_manager.errors import OpenStackInvalidConfigError

logger = logging.getLogger(__name__)


class CloudConfig(TypedDict):
    """The parsed clouds.yaml configuration dictionary.

    Attributes:
        clouds: A mapping of key "clouds" to cloud name mapped to cloud configuration.
    """

    clouds: dict[str, dict]


def _validate_cloud_config(cloud_config: dict) -> CloudConfig:
    """Validate the format of the cloud configuration.

    Args:
        cloud_config: The configuration in clouds.yaml format to validate.

    Raises:
        OpenStackInvalidConfigError: if the format of the config is invalid.

    Returns:
        A typed cloud_config dictionary.
    """
    # dict of format: {clouds: <cloud-name>: <cloud-config>}
    try:
        clouds = list(cloud_config["clouds"].keys())
    except KeyError as exc:
        raise OpenStackInvalidConfigError("Missing key 'clouds' from config.") from exc
    if not clouds:
        raise OpenStackInvalidConfigError("No clouds defined in clouds.yaml.")
    return cast(CloudConfig, cloud_config)
