#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import datetime
import itertools
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import openstack
import pytest
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection

from github_runner_manager.errors import OpenStackError
from github_runner_manager.openstack_cloud.openstack_cloud import (
    _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION,
    OpenstackCloud,
    OpenStackCredentials,
)

FAKE_ARG = "fake"
FAKE_PREFIX = "fake_prefix"


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


def test_keypair_cleanup_freshly_created_keypairs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: Keypairs with different creation time.
    act: Call cleanup.
    assert: Only keypairs older than a threshold are deleted.
    """
    ### arrange ###
    # Mock expanduser as this is used in OpenstackCloud constructor
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.Path.expanduser", MagicMock()
    )

    creds = OpenStackCredentials(
        username=FAKE_ARG,
        password=FAKE_ARG,
        project_name=FAKE_ARG,
        user_domain_name=FAKE_ARG,
        project_domain_name=FAKE_ARG,
        auth_url=FAKE_ARG,
        region_name=FAKE_ARG,
    )
    cloud = OpenstackCloud(creds, FAKE_PREFIX, FAKE_ARG)
    cloud._ssh_key_dir = tmp_path / "ssh_key_dir"
    cloud._ssh_key_dir.mkdir()

    openstack_connect_mock = MagicMock(spec=openstack.connect)
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
        openstack_connect_mock,
    )

    now = _mock_datetime_now(monkeypatch)
    keypairs_older_or_same_min_age = (
        (
            cloud._ssh_key_dir / f"{FAKE_PREFIX}-old-{i}.key",
            now - datetime.timedelta(seconds=seconds),
        )
        for i, seconds in enumerate(
            (
                _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION,
                _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION + 1,
                _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION * 2,
            )
        )
    )
    keypairs_younger_than_min_age = (
        (
            cloud._ssh_key_dir / f"{FAKE_PREFIX}-new-{i}.key",
            now - datetime.timedelta(seconds=seconds),
        )
        for i, seconds in enumerate((1, _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION - 1))
    )
    # Create keypairs
    keypair_list: list[Keypair] = []
    for keypair, mtime in itertools.chain(
        keypairs_older_or_same_min_age, keypairs_younger_than_min_age
    ):
        keypair.write_text("foobar")
        os.utime(keypair, (mtime.timestamp(), mtime.timestamp()))
        keypair_list.append(
            Keypair(
                created_at=mtime.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                name=keypair.name.removesuffix(".key"),
            )
        )

    openstack_connection_mock = MagicMock(spec=Connection)
    openstack_connection_mock.__enter__.return_value = openstack_connection_mock
    openstack_connection_mock.list_keypairs.return_value = keypair_list
    openstack_connection_mock.list_keypairs.return_value = keypair_list
    openstack_connect_mock.return_value = openstack_connection_mock

    ### act ###
    cloud.cleanup()

    ### assert ###
    # Check if only the old keypairs are deleted
    keypair_delete_calls = [
        call[0][0] for call in openstack_connection_mock.delete_keypair.call_args_list
    ]
    for keypair, _ in keypairs_older_or_same_min_age:
        assert not keypair.exists()
        assert keypair.name.removesuffix(".key") in keypair_delete_calls
    for keypair, _ in keypairs_younger_than_min_age:
        assert keypair.exists()
        assert keypair.name.removesuffix(".key") not in keypair_delete_calls


def _mock_datetime_now(monkeypatch):
    """Mock datetime.now() to return a fixed datetime."""
    now = datetime.datetime.now(datetime.timezone.utc)
    now_mock = MagicMock()
    now_mock.return_value = now
    datetime_mock = MagicMock()
    datetime_mock.now.return_value = now
    datetime_mock.fromisoformat = datetime.datetime.fromisoformat
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.datetime", datetime_mock
    )
    return now
