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
        "name": "app_name",
        "extra_labels": ["label1", "label2"],
        "github_config": {"path": {"group": "group", "org": "canonical"}, "token": "githubtoken"},
        "non_reactive_configuration": {
            "combinations": [
                {
                    "base_virtual_machines": 1,
                    "flavor": {"labels": ["flavorlabel"], "name": "flavor"},
                    "image": {"labels": ["arm64", "noble"], "name": "image_id"},
                }
            ]
        },
        "reactive_configuration": {
            "flavors": [{"labels": ["flavorlabel"], "name": "flavor"}],
            "images": [{"labels": ["arm64", "noble"], "name": "image_id"}],
            "max_total_virtual_machines": 2,
            "queue": {
                "mongodb_uri": "mongodb://user:password@localhost:27017",
                "queue_name": "app_name",
            },
        },
        "service_config": {
            "dockerhub_mirror": "https://docker.example.com",
            "proxy_config": {
                "http": "http://httpproxy.example.com:3128",
                "https": "http://httpsproxy.example.com:3128",
                "no_proxy": "127.0.0.1",
            },
            "runner_proxy_config": {
                "http": "http://httpproxy.example.com:3128",
                "https": "http://httpsproxy.example.com:3128",
                "no_proxy": "127.0.0.1",
            },
            "use_aproxy": False,
            "repo_policy_compliance": {"token": "token", "url": "https://compliance.example.com"},
            "ssh_debug_connections": [
                {
                    "ed25519_fingerprint": "SHA256:ed25519",
                    "host": "10.10.10.10",
                    "port": 3000,
                    "rsa_fingerprint": "SHA256:rsa",
                }
            ],
        },
    }


@pytest.fixture(name="openstack_config", scope="module")
def openstack_config_fixture() -> dict:
    return {
        "vm_prefix": "test_unit",
        "network": "test_network",
        "credentials": {
            "auth_url": "http://example.com/test",
            "project_name": "test_project",
            "username": "test_username",
            "password": "test_password",
            "user_domain_name": "test_user_domain_name",
            "project_domain_name": "test_project_domain_name",
            "region_name": "test_region",
        },
    }


@pytest.fixture(name="config_file", scope="module")
def config_file_fixture(tmp_path_factory, config: dict) -> Path:
    config_file = tmp_path_factory.mktemp("config") / "config.yaml"
    with open(config_file, "w") as file:
        yaml.safe_dump(config, file)
    return config_file


@pytest.fixture(name="openstack_config_file", scope="module")
def openstack_config_file_fixture(tmp_path_factory, openstack_config: dict) -> Path:
    openstack_config_file = tmp_path_factory.mktemp("openstack") / "config.yaml"
    with open(openstack_config_file, "w") as file:
        yaml.safe_dump(openstack_config, file)
    return openstack_config_file


@pytest.fixture(name="install_app", scope="module")
def install_app_fixture() -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "."])


@pytest.fixture(name="app", scope="function")
def app_fixture(
    install_app: None, config_file: Path, openstack_config_file: Path
) -> Iterator[subprocess.Popen]:

    # TODO: debug
    # with open(config_file, "r") as file:
    #     config = file.read()
    # with open(openstack_config_file, "r") as file:
    #     openstack_config = file.read()
    # import getpass
    # import grp
    # import os

    # from src.github_runner_manager.configuration import ApplicationConfiguration
    # from src.github_runner_manager.manager.runner_scaler import RunnerScaler
    # from src.github_runner_manager.openstack_cloud.configuration import OpenStackConfiguration
    # from src.github_runner_manager.configuration import UserInfo

    # user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()))
    # runner_scaler = RunnerScaler.build(
    #     ApplicationConfiguration.from_yaml_file(config),
    #     OpenStackConfiguration.from_yaml_file(openstack_config),
    #     user,
    # )

    # pytest.set_trace()
    # pass

    process = start_app(config_file, openstack_config_file, [])
    yield process
    process.kill()
