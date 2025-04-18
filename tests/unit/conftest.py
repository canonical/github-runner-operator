# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
import secrets
import typing
import unittest.mock
from pathlib import Path

import pytest
from github_runner_manager.configuration.github import GitHubOrg
from github_runner_manager.manager.runner_scaler import RunnerScaler

import charm_state
import utilities
from tests.unit.mock import MockGhapiClient


@pytest.fixture(name="exec_command")
def exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


def disk_usage_mock(total_disk: int):
    """Mock disk usage factory.

    Args:
        total_disk: Total disk size in bytes.

    Returns:
        A disk usage magic mock instance.
    """
    disk = unittest.mock.MagicMock()
    disk.total = total_disk
    disk_usage = unittest.mock.MagicMock(return_value=disk)
    return disk_usage


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path, exec_command):
    runner_scaler_mock = unittest.mock.MagicMock(spec=RunnerScaler)

    cron_path = tmp_path / "cron.d"
    cron_path.mkdir()

    monkeypatch.setattr("charm.RunnerScaler", runner_scaler_mock)
    monkeypatch.setattr("charm.execute_command", exec_command)
    monkeypatch.setattr("charm_state.CHARM_STATE_PATH", Path(tmp_path / "charm_state.json"))
    monkeypatch.setattr("event_timer.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("event_timer.execute_command", exec_command)
    monkeypatch.setattr(
        "github_runner_manager.metrics.events.METRICS_LOG_PATH", Path(tmp_path / "metrics.log")
    )
    monkeypatch.setattr("github_runner_manager.github_client.GhApi", MockGhapiClient)
    monkeypatch.setattr("github_runner_manager.utilities.time", unittest.mock.MagicMock())


@pytest.fixture(autouse=True, name="cloud_name")
def cloud_name_fixture() -> str:
    """The testing cloud name."""
    return "microstack"


@pytest.fixture(name="clouds_yaml")
def clouds_yaml_fixture(cloud_name: str) -> dict:
    """Testing clouds.yaml."""
    return {
        "clouds": {
            cloud_name: {
                "auth": {
                    "auth_url": secrets.token_hex(16),
                    "project_name": secrets.token_hex(16),
                    "project_domain_name": secrets.token_hex(16),
                    "username": secrets.token_hex(16),
                    "user_domain_name": secrets.token_hex(16),
                    "password": secrets.token_hex(16),
                }
            }
        }
    }


@pytest.fixture(name="multi_clouds_yaml")
def multi_clouds_yaml_fixture(clouds_yaml: dict) -> dict:
    """Testing clouds.yaml with multiple clouds."""
    multi_clouds_yaml = copy.deepcopy(clouds_yaml)
    multi_clouds_yaml["clouds"]["unused_cloud"] = {
        "auth": {
            "auth_url": secrets.token_hex(16),
            "project_name": secrets.token_hex(16),
            "project_domain_name": secrets.token_hex(16),
            "username": secrets.token_hex(16),
            "user_domain_name": secrets.token_hex(16),
            "password": secrets.token_hex(16),
        }
    }
    return multi_clouds_yaml


@pytest.fixture(name="skip_retry")
def skip_retry_fixture(monkeypatch: pytest.MonkeyPatch):
    """Fixture for skipping retry for functions with retry decorator."""

    def patched_retry(*args, **kwargs):
        """A fallthrough decorator.

        Args:
            args: Positional arguments placeholder.
            kwargs: Keyword arguments placeholder.

        Returns:
            The fallthrough decorator.
        """

        def patched_retry_decorator(func: typing.Callable):
            """The fallthrough decorator.

            Args:
                func: The function to decorate.

            Returns:
                the function without any additional features.
            """
            return func

        return patched_retry_decorator

    monkeypatch.setattr(utilities, "retry", patched_retry)


@pytest.fixture(name="complete_charm_state")
def complete_charm_state_fixture():
    """Returns a fixture with a fully populated CharmState."""
    return charm_state.CharmState(
        arch="arm64",
        is_metrics_logging_available=False,
        proxy_config=charm_state.ProxyConfig(
            http="http://httpproxy.example.com:3128",
            https="http://httpsproxy.example.com:3128",
            no_proxy="127.0.0.1",
        ),
        runner_proxy_config=charm_state.ProxyConfig(
            http="http://runnerhttpproxy.example.com:3128",
            https="http://runnerhttpsproxy.example.com:3128",
            no_proxy="10.0.0.1",
        ),
        charm_config=charm_state.CharmConfig(
            dockerhub_mirror="https://docker.example.com",
            labels=("label1", "label2"),
            openstack_clouds_yaml=charm_state.OpenStackCloudsYAML(
                clouds={
                    "microstack": {
                        "auth": {
                            "auth_url": "auth_url",
                            "project_name": "project_name",
                            "project_domain_name": "project_domain_name",
                            "username": "username",
                            "user_domain_name": "user_domain_name",
                            "password": "password",
                        },
                        "region_name": "region",
                    }
                },
            ),
            path=GitHubOrg(org="canonical", group="group"),
            reconcile_interval=5,
            repo_policy_compliance=charm_state.RepoPolicyComplianceConfig(
                token="token",
                url="https://compliance.example.com",
            ),
            token="githubtoken",
            manager_proxy_command="ssh -W %h:%p example.com",
            use_aproxy=True,
        ),
        runner_config=charm_state.OpenstackRunnerConfig(
            base_virtual_machines=1,
            max_total_virtual_machines=2,
            flavor_label_combinations=[
                charm_state.FlavorLabel(
                    flavor="flavor",
                    label="flavorlabel",
                )
            ],
            openstack_network="network",
            openstack_image=charm_state.OpenstackImage(
                id="image_id",
                tags=["arm64", "noble"],
            ),
        ),
        reactive_config=charm_state.ReactiveConfig(
            mq_uri="mongodb://user:password@localhost:27017",
        ),
        ssh_debug_connections=[
            charm_state.SSHDebugConnection(
                host="10.10.10.10",
                port=3000,
                # Not very realistic
                rsa_fingerprint="SHA256:rsa",
                ed25519_fingerprint="SHA256:ed25519",
            ),
        ],
    )
