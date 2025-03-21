#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration test setups and configurations."""

import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest
import yaml

from tests.integration.helper import start_app


@pytest.fixture(name="config", scope="module")
def config_fixture() -> dict:
    return {
        "name": "test_org/test_repo",
        "github_path": "test_org",
        "github_token": "test_token",
        "github_runner_group": None,
        "runner_count": 1,
        "runner_labels": ("test", "unit-test", "test-data"),
        "openstack_auth_url": "http://www.example.com/test_url",
        "openstack_project_name": "test-project",
        "openstack_username": "test-username",
        "openstack_password": "test-password",
        "openstack_user_domain_name": "default",
        "openstack_domain_name": "default",
        "openstack_flavor": "test_flavor",
        "openstack_network": "test_network",
        "dockerhub_mirror": None,
        "repo_policy_compliance_url": None,
        "repo_policy_compliance_token": None,
        "http_proxy": None,
    }


@pytest.fixture(name="config_file", scope="module")
def config_file_fixture(tmp_path_factory, config: dict) -> Path:
    config_file = tmp_path_factory.mktemp("config") / "test.yaml"
    with open(config_file, "w") as file:
        yaml.safe_dump(config, file)
    return config_file


@pytest.fixture(name="install_app", scope="module")
def install_app_fixture() -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "."])


@pytest.fixture(name="app", scope="function")
def app_fixture(install_app: None, config_file: Path) -> Iterator[subprocess.Popen]:
    process = start_app(config_file, [])
    yield process
    process.kill()
