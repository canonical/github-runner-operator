#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for OpenStack integration."""


import yaml
from juju.application import Application
from juju.model import Model

from charm_state import OPENSTACK_CLOUDS_YAML_CONFIG_NAME
from tests.integration.helpers import run_in_unit


async def test_openstack_integration(
    model: Model, app_no_runner: Application, openstack_clouds_yaml: str
):
    """
    arrange: Load the OpenStack clouds.yaml config. Parse project name from the config.
    act: Set the openstack-clouds-yaml config in the charm
    assert: Check the unit log for successful OpenStack connection and that the project is listed.
    """
    openstack_clouds_yaml_yaml = yaml.safe_load(openstack_clouds_yaml)
    first_cloud = next(iter(openstack_clouds_yaml_yaml["clouds"].values()))
    project_name = first_cloud["auth"]["project_name"]

    await app_no_runner.set_config({OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_clouds_yaml})
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
