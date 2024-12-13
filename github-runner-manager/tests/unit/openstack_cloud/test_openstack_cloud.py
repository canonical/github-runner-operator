#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
from typing import Any
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import openstack
import pytest

from github_runner_manager.errors import OpenStackError
from github_runner_manager.openstack_cloud.openstack_cloud import (
    OpenstackCloud,
    OpenStackCredentials,
)

FAKE_ARG = "fake"


@pytest.mark.parametrize(
    "public_method, args",
    [
        pytest.param("launch_instance", (FAKE_ARG,) * 5, id="launch_instance"),
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
        with pytest.raises(OpenStackError) as exc:
            getattr(cloud, public_method)(*args)
        assert "Failed OpenStack API call" in str(exc.value)
