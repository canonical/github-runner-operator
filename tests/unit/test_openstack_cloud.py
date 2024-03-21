#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
from pathlib import Path

import pytest
import yaml

import openstack_cloud
from errors import OpenStackInvalidConfigError


def test_initialize(clouds_yaml_path: Path, clouds_yaml: dict):
    """
    arrange: Mocked clouds.yaml data and path.
    act: Call initialize.
    assert: The clouds.yaml file is written to disk.
    """
    openstack_cloud.initialize(clouds_yaml)

    assert yaml.safe_load(clouds_yaml_path.read_text(encoding="utf-8")) == clouds_yaml


@pytest.mark.parametrize(
    "invalid_yaml, expected_err_msg",
    [
        pytest.param(
            {"wrong-key": {"cloud_name": {"auth": {}}}}, "Missing key 'clouds' from config."
        ),
        pytest.param({}, "Missing key 'clouds' from config."),
        pytest.param({"clouds": {}}, "No clouds defined in clouds.yaml."),
    ],
)
def test_initialize_validation_error(invalid_yaml: dict, expected_err_msg):
    """
    arrange: Mocked clouds.yaml data with invalid data.
    act: Call initialize.
    assert: InvalidConfigError is raised.
    """
<<<<<<< HEAD
=======

>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b
    with pytest.raises(OpenStackInvalidConfigError) as exc:
        openstack_cloud.initialize(invalid_yaml)
    assert expected_err_msg in str(exc)
