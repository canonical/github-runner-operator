# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for unit-testing OpenStack runner manager."""

import logging
import textwrap
from unittest.mock import MagicMock

import pytest

from github_runner_manager.configuration import ProxyConfig, SupportServiceConfig, UserInfo
from github_runner_manager.manager.models import (
    InstanceID,
    RunnerContext,
    RunnerIdentity,
    RunnerMetadata,
)
from github_runner_manager.metrics import runner
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackCloud
from github_runner_manager.openstack_cloud.openstack_runner_manager import (
    OpenStackRunnerManager,
    OpenStackRunnerManagerConfig,
    runner_metrics,
)

logger = logging.getLogger(__name__)

OPENSTACK_INSTANCE_PREFIX = "test"


@pytest.fixture(name="runner_manager")
def openstack_runner_manager_fixture(
    monkeypatch: pytest.MonkeyPatch, user_info: UserInfo
) -> OpenStackRunnerManager:
    """Mock required dependencies/configs and return an OpenStackRunnerManager instance."""
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_runner_manager.OpenstackCloud",
        MagicMock(),
    )

    service_config_mock = MagicMock(list(SupportServiceConfig.__fields__.keys()))
    service_config_mock.proxy_config = None
    service_config_mock.runner_proxy_config = None
    service_config_mock.use_aproxy = False
    service_config_mock.ssh_debug_connections = []
    service_config_mock.repo_policy_compliance = None
    config = OpenStackRunnerManagerConfig(
        allow_external_contributor=False,
        prefix="test",
        credentials=MagicMock(),
        server_config=MagicMock(),
        service_config=service_config_mock,
    )

    return OpenStackRunnerManager(config=config, user=user_info)


@pytest.fixture(name="runner_metrics_mock")
def runner_metrics_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the runner_metrics module."""
    runner_metrics_mock = MagicMock(spec=runner)
    monkeypatch.setattr(runner, "pull_runner_metrics", runner_metrics_mock)
    return runner_metrics_mock


@pytest.mark.parametrize(
    "aproxy_redirect_ports, aproxy_exclude_addresses, aproxy_used, except_aproxy_script",
    [
        pytest.param(
            [],
            ["10.0.0.0/8"],
            False,
            "",
            id="empty aproxy_redirect_ports disables aproxy",
        ),
        pytest.param(
            ["80", "443"],
            ["10.0.0.0/8", "192.168.0.0/16"],
            True,
            "10.0.0.0/8, 192.168.0.0/16",
            id="aproxy with custom aproxy_exclude_addresses",
        ),
        pytest.param(
            ["0-3127", "3129-65535"],
            ["10.0.0.0/8", "192.168.0.0/16"],
            True,
            "0-3127, 3129-65535",
            id="aproxy with custom aproxy_redirect_ports",
        ),
        pytest.param(
            ["80", "443"],
            ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
            True,
            textwrap.dedent("""\
    table ip aproxy {
          set exclude {
              type ipv4_addr;
              flags interval; auto-merge;
              elements = { 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 }
          }
          chain prerouting {
                  type nat hook prerouting priority dstnat; policy accept;
                  ip daddr != @exclude tcp dport { 80, 443 } counter dnat to \\$default-ipv4:54969
          }
          chain output {
                  type nat hook output priority -100; policy accept;
                  ip daddr != @exclude tcp dport { 80, 443 } counter dnat to \\$default-ipv4:54969
          }
    }
            """),
            id="aproxy default config",
        ),
        pytest.param(
            ["80", "443"],
            [],
            True,
            textwrap.dedent("""\
    table ip aproxy {
          set exclude {
              type ipv4_addr;
              flags interval; auto-merge;
              elements = { 127.0.0.0/8,  }
          }
          chain prerouting {
                  type nat hook prerouting priority dstnat; policy accept;
                  ip daddr != @exclude tcp dport { 80, 443 } counter dnat to \\$default-ipv4:54969
          }
          chain output {
                  type nat hook output priority -100; policy accept;
                  ip daddr != @exclude tcp dport { 80, 443 } counter dnat to \\$default-ipv4:54969
          }
    }
            """),
            id="aproxy with no aproxy_exclude_addresses",
        ),
    ],
)
def test_create_runner_with_aproxy(
    aproxy_redirect_ports: list[str],
    aproxy_exclude_addresses: list[str],
    aproxy_used: str,
    except_aproxy_script: str,
    runner_manager: OpenStackRunnerManager,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Prepare service config with aproxy enabled and a runner proxy config.
    act: Create a runner.
    assert: The cloud init in the runner should enable the aproxy with the proxy.
    """
    # Pending to pass service_config as a dependency instead of mocking it this way.
    service_config = runner_manager._config.service_config
    service_config.use_aproxy = True
    service_config.aproxy_redirect_ports = aproxy_redirect_ports
    service_config.aproxy_exclude_addresses = aproxy_exclude_addresses
    service_config.runner_proxy_config = ProxyConfig(http="http://proxy.example.com:3128")

    prefix = "test"
    agent_command = "agent"
    runner_context = RunnerContext(shell_run_script=agent_command)
    instance_id = InstanceID.build(prefix=prefix)
    identity = RunnerIdentity(instance_id=instance_id, metadata=RunnerMetadata())

    openstack_cloud = MagicMock(spec=OpenstackCloud)
    monkeypatch.setattr(runner_manager, "_openstack_cloud", openstack_cloud)

    runner_manager.create_runner(identity, runner_context)
    openstack_cloud.launch_instance.assert_called_once()

    cloud_init = openstack_cloud.launch_instance.call_args.kwargs["cloud_init"]
    assert ("snap set aproxy proxy=proxy.example.com:3128" in cloud_init) == aproxy_used
    if aproxy_used:
        assert except_aproxy_script in cloud_init


def test_create_runner_without_aproxy(
    runner_manager: OpenStackRunnerManager, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Prepare service config with aproxy disables and a runner proxy config.
    act: Create a runner.
    assert: The cloud init in the runner should not reference aproxy.
    """
    # Pending to pass service_config as a dependency instead of mocking it this way.
    service_config = runner_manager._config.service_config
    service_config.use_aproxy = False
    service_config.runner_proxy_config = ProxyConfig(http="http://proxy.example.com:3128")

    prefix = "test"
    agent_command = "agent"
    runner_context = RunnerContext(shell_run_script=agent_command)
    instance_id = InstanceID.build(prefix=prefix)
    identity = RunnerIdentity(instance_id=instance_id, metadata=RunnerMetadata())

    openstack_cloud = MagicMock(spec=OpenstackCloud)
    monkeypatch.setattr(runner_manager, "_openstack_cloud", openstack_cloud)

    runner_manager.create_runner(identity, runner_context)
    openstack_cloud.launch_instance.assert_called_once()
    assert "aproxy" not in openstack_cloud.launch_instance.call_args.kwargs["cloud_init"]


def test_delete_vms(runner_manager: OpenStackRunnerManager):
    """
    arrange: given a mocked cloud service.
    act: when delete_vms method is called.
    assert: the mocked service call is made and the deleted instance IDs are returned.
    """
    test_instance_ids = [InstanceID(prefix="test-prefix", reactive=None, suffix="test-suffix")]
    mock_cloud = MagicMock()
    mock_cloud.delete_instances = MagicMock(return_value=test_instance_ids)
    runner_manager._openstack_cloud = mock_cloud

    assert test_instance_ids == runner_manager.delete_vms(instance_ids=test_instance_ids)
    mock_cloud.delete_instances.assert_called_once()


def test_extract_metrics(runner_manager: OpenStackRunnerManager, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked metrics service.
    act: when extract_metrics method is called.
    assert: converted metrics are returned.
    """
    pull_metrics_mock = MagicMock(
        return_value=[(test_metric_one := MagicMock()), (test_metric_two := MagicMock())]
    )
    monkeypatch.setattr(runner_metrics, "pull_runner_metrics", pull_metrics_mock)

    metrics = runner_manager.extract_metrics(instance_ids=MagicMock())
    assert metrics == [test_metric_one, test_metric_two]
