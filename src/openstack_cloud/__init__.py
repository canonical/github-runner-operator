# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing Openstack cloud."""

import logging
import os
import shutil
from pathlib import Path
from typing import TypedDict, cast

import yaml

from errors import OpenStackInvalidConfigError

logger = logging.getLogger(__name__)


CLOUDS_YAML_PATH = Path(Path.home() / ".config/openstack/clouds.yaml")


# Make sure we can import openstack, if not remove the old openstacksdk library and retry.
# This is a workaround for https://bugs.launchpad.net/juju/+bug/2058335
def _remove_old_openstacksdk_lib() -> None:  # pragma: no cover
    """Remove the old openstacksdk library if it exists."""
    try:
        unit_name = os.environ["JUJU_UNIT_NAME"].replace("/", "-")
        venv_dir = Path(f"/var/lib/juju/agents/unit-{unit_name}/charm/venv/")
        openstacksdk_dirs = list(venv_dir.glob("openstacksdk-*.dist-info"))
        # use error log level as logging may not be fully initialized yet
        logger.error("Found following openstack dirs: %s", openstacksdk_dirs)
        if len(openstacksdk_dirs) > 1:
            openstacksdk_dirs.sort()
            for openstacksdk_dir in openstacksdk_dirs[:-1]:
                logger.error("Removing old openstacksdk library: %s", openstacksdk_dir)
                shutil.rmtree(openstacksdk_dir)
        else:
            logger.error(
                "No old openstacksdk library to remove. "
                "Please reach out to the charm dev team for further advice."
            )
    except OSError:
        logger.exception(
            "Failed to remove old openstacksdk library. "
            "Please reach out to the charm dev team for further advice."
        )


try:
    import openstack
except AttributeError:
    logger.error(
        "Failed to import openstack. "
        "Assuming juju bug https://bugs.launchpad.net/juju/+bug/2058335. "
        "Removing old openstacksdk library and retrying."
    )
    _remove_old_openstacksdk_lib()
    try:
        # The import is there to make sure the charm fails if the openstack import is not working.
        import openstack  # noqa: F401
    except AttributeError:
        logger.exception(
            "Failed to import openstack. Please reach out to the charm team for further advice."
        )
        raise


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


def _write_config_to_disk(cloud_config: CloudConfig) -> None:
    """Write the cloud configuration to disk.

    Args:
        cloud_config: The configuration in clouds.yaml format to write to disk.
    """
    CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLOUDS_YAML_PATH.write_text(encoding="utf-8", data=yaml.dump(cloud_config))


def initialize(cloud_config: dict) -> None:
    """Initialize Openstack integration.

    Validates config and writes it to disk.

    Raises:
        OpenStackInvalidConfigError: If there was an given cloud config.

    Args:
        cloud_config: The configuration in clouds.yaml format to apply.
    """
    try:
        valid_config = _validate_cloud_config(cloud_config)
    # 2024/04/02 - We should define a new error, wrap it and re-raise it.
    except OpenStackInvalidConfigError:  # pylint: disable=try-except-raise
        raise
    _write_config_to_disk(valid_config)
