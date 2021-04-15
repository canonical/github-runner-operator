from pathlib import Path

import yaml

import pytest


@pytest.fixture
def metadata():
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture
def application(ops_test, metadata):
    charm_name = metadata["name"]
    app = ops_test.model.applications[charm_name]
    return app


@pytest.fixture
def units(application):
    units = application.units
    return units
