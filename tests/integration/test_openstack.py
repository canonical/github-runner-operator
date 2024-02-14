#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""

import json
from pathlib import Path

from juju.application import Application
from juju.model import Model

from charm_state import OPENSTACK_CLOUDS_YAML_CONFIG_NAME
from tests.integration.helpers import run_in_unit


def _load_openstack_rc_file(rc_file_path) -> dict:
    """Load the OpenStack RC file and return the environment variables.

    Args:
        rc_file_path: The path to the OpenStack RC file.

    Returns:
        The environment variables from the OpenStack RC file.
    """
    env = {}
    with open(rc_file_path, "r") as f:
        for line in f:
            # Check if the line starts with 'export'
            if line.startswith("export"):
                # Remove 'export ' prefix and split key and value
                parts = line[7:].strip().split("=", 1)
                if len(parts) == 2:
                    # Set the environment variable in the Python process
                    env[parts[0]] = parts[1]

    return env


async def test_openstack_integration(model: Model, app_no_runner: Application, openstack_rc: Path):
    """
    arrange: Load the OpenStack RC file and set the environment variables
    act: Set the openstack-clouds-yaml config in the charm
    assert: Check the unit log for successful OpenStack connection
    """
    # microstack generates an OpenStack RC file instead of a clouds.yaml file.
    openstack_env = _load_openstack_rc_file(openstack_rc)
    project_name = openstack_env["OS_PROJECT_NAME"]
    clouds = {
        "clouds": {
            "microstack": {
                "auth": {
                    "auth_url": openstack_env["OS_AUTH_URL"],
                    "project_name": project_name,
                    "project_domain_name": openstack_env["OS_PROJECT_DOMAIN_NAME"],
                    "username": openstack_env["OS_USERNAME"],
                    "user_domain_name": openstack_env["OS_USER_DOMAIN_NAME"],
                    "password": openstack_env["OS_PASSWORD"],
                }
            }
        }
    }
    await app_no_runner.set_config({OPENSTACK_CLOUDS_YAML_CONFIG_NAME: json.dumps(clouds)})
    await model.wait_for_idle(apps=[app_no_runner.name])
    unit = app_no_runner.units[0]
    unit_name_with_dash = unit.name.replace("/", "-")
    ret_code, unit_log = await run_in_unit(
        unit=unit,
        command=f"cat /var/log/juju/unit-{unit_name_with_dash}.log",
    )
    assert ret_code == 0, "Failed to read the unit log"
    assert unit_log is not None, "Failed to read the unit log, no stdout message"
    assert "OpenStack connection successful." in unit_log
    assert "OpenStack projects:" in unit_log
    assert project_name in unit_log
