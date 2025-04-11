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

from github_runner_manager.errors import OpenStackError
from github_runner_manager.openstack_cloud.openstack_cloud import (
    OpenstackCloud,
    OpenStackCredentials, _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION,
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
    arrange: Keypair files with different st_mtime.
    act: Call cleanup.
    assert: Only keypair files older than the threshold are deleted.
    """
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

    now = datetime.datetime.now(datetime.timezone.utc)
    keypairs_older_then_threshold = (
        (cloud._ssh_key_dir / f"{FAKE_PREFIX}-old-server1.key", now - datetime.timedelta(seconds=_MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION + 1)),
        (cloud._ssh_key_dir / f"{FAKE_PREFIX}-old-server2.key", now - datetime.timedelta(seconds=_MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION)),
    )
    keypairs_newer_than_threshold = (
        (cloud._ssh_key_dir / f"{FAKE_PREFIX}-new-server1.key", now - datetime.timedelta(seconds=1)),
        (cloud._ssh_key_dir / f"{FAKE_PREFIX}-new-server2.key", now - datetime.timedelta(seconds=_MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION - 1)),
    )
    # Create keypair files
    for keypair, mtime in itertools.chain(keypairs_older_then_threshold, keypairs_newer_than_threshold):
        keypair.write_text("foobar")
        os.utime(keypair, (mtime.timestamp(), mtime.timestamp()))
    cloud.cleanup()
    # Check if only the old keypairs are deleted
    for keypair, _ in keypairs_older_then_threshold:
        assert not keypair.exists()
    for keypair, _ in keypairs_newer_than_threshold:
        assert keypair.exists()
