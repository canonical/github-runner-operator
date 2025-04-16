#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import copy
import logging
from typing import Any
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import openstack
import pytest
from openstack.network.v2.security_group import SecurityGroup as OpenstackSecurityGroup
from openstack.network.v2.security_group_rule import SecurityGroupRule

from github_runner_manager.errors import OpenStackError
from github_runner_manager.openstack_cloud.openstack_cloud import (
    DEFAULT_SECURITY_RULES,
    OpenstackCloud,
    OpenStackCredentials,
    get_missing_security_rules,
)

FAKE_ARG = "fake"

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "public_method, args",
    [
        pytest.param("launch_instance", (FAKE_ARG,) * 4, id="launch_instance"),
        pytest.param("get_instance", (FAKE_ARG,), id="get_instance"),
        pytest.param("delete_instance", (FAKE_ARG,), id="delete_instance"),
        pytest.param("get_instances", (), id="get_instances"),
        pytest.param("cleanup", (), id="cleanup"),
    ],
)
def test_raises_openstack_error(
    public_method: str, args: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock OpenstackCloud and openstack.connect to raise an Openstack api exception.
    act: Call a public method which connects to Openstack.
    assert: OpenStackError is raised.
    """
    creds = OpenStackCredentials(
        username=FAKE_ARG,
        password=FAKE_ARG,
        project_name=FAKE_ARG,
        user_domain_name=FAKE_ARG,
        project_domain_name=FAKE_ARG,
        auth_url=FAKE_ARG,
        region_name=FAKE_ARG,
    )
    # Mock expanduser as this is used in OpenstackCloud constructor
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.Path.expanduser", MagicMock()
    )

    cloud = OpenstackCloud(creds, FAKE_ARG, FAKE_ARG)
    openstack_connect_mock = MagicMock(spec=openstack.connect)

    excs = (openstack.exceptions.SDKException, keystoneauth1.exceptions.ClientException)
    for exc in excs:
        openstack_connect_mock.side_effect = exc("an exception occurred")
        monkeypatch.setattr(
            "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
            openstack_connect_mock,
        )
        with pytest.raises(OpenStackError) as innerexc:
            getattr(cloud, public_method)(*args)
        assert "Failed OpenStack API call" in str(innerexc.value)


@pytest.mark.parametrize(
    "security_rules, extra_ports, expected_missing_rules",
    [
        pytest.param(
            [],
            None,
            copy.deepcopy(DEFAULT_SECURITY_RULES),
            id="Empty security group. All rules required.",
        ),
        pytest.param(
            [],
            [8080],
            copy.deepcopy(DEFAULT_SECURITY_RULES)
            | {
                "tcp8080": {
                    "direction": "ingress",
                    "ethertype": "IPv4",
                    "port_range_max": 8080,
                    "port_range_min": 8080,
                    "protocol": "tcp",
                }
            },
            id="Empty security group. Extra port required",
        ),
        pytest.param(
            [SecurityGroupRule(**value) for (name, value) in DEFAULT_SECURITY_RULES.items()],
            None,
            {},
            id="Nothing to add",
        ),
        pytest.param(
            [
                SecurityGroupRule(**value)
                for (name, value) in DEFAULT_SECURITY_RULES.items()
                if name != "ssh"
            ],
            None,
            {"ssh": DEFAULT_SECURITY_RULES["ssh"]},
            id="Missing ssh rule",
        ),
    ],
)
def test_missing_security_rules(security_rules, extra_ports, expected_missing_rules):
    """
    arrange: Mock OpenstackCloud and openstack.connect to raise an Openstack api exception.
    act: Call a public method which connects to Openstack.
    assert: OpenStackError is raised.
    """
    security_group = OpenstackSecurityGroup()
    security_group.security_group_rules = security_rules

    missing = get_missing_security_rules(security_group, extra_ports)
    assert missing == expected_missing_rules
