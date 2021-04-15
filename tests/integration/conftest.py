from pathlib import Path

import pytest
import yaml


@pytest.fixture
def metadata():
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture
def model(ops_test):
    return ops_test.model


@pytest.fixture
def application(model, metadata):
    charm_name = metadata["name"]
    app = model.applications[charm_name]
    return app


@pytest.fixture
def units(application):
    units = application.units
    return units
