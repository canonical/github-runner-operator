#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
import copy
import datetime
import itertools
import logging
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import keystoneauth1.exceptions
import openstack
import openstack.exceptions
import pytest
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup as OpenstackSecurityGroup
from openstack.network.v2.security_group_rule import SecurityGroupRule
from pytest import LogCaptureFixture

import github_runner_manager.openstack_cloud.openstack_cloud
from github_runner_manager.errors import OpenStackError, SSHError
from github_runner_manager.openstack_cloud.openstack_cloud import (
    _MAX_NOVA_COMPUTE_API_VERSION,
    _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION,
    _TEST_STRING,
    DEFAULT_SECURITY_RULES,
    InstanceID,
    OpenstackCloud,
    OpenStackCredentials,
    _DeleteKeypairConfig,
    get_missing_security_rules,
)
from tests.unit.fake_runner_managers import FakeOpenstackCloud

FAKE_ARG = "fake"
FAKE_PREFIX = "fake_prefix"

logger = logging.getLogger(__name__)


@pytest.fixture(name="openstack_cloud", scope="function")
def openstack_cloud_fixture(monkeypatch):
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
    return OpenstackCloud(creds, FAKE_PREFIX, FAKE_ARG)


@pytest.fixture(name="mock_openstack_conn", scope="function")
def mock_openstack_conn_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch OpenStack connection."""
    connection_mock = MagicMock()
    connection_mock.__enter__.return_value = connection_mock
    monkeypatch.setattr(
        github_runner_manager.openstack_cloud.openstack_cloud.openstack,
        "connect",
        MagicMock(return_value=connection_mock),
    )
    return connection_mock


@pytest.mark.parametrize(
    "public_method, args",
    [
        pytest.param(
            "launch_instance",
            {
                "runner_identity": MagicMock(),
                "server_config": FAKE_ARG,
                "cloud_init": FAKE_ARG,
            },
            id="launch_instance",
        ),
        pytest.param("get_instance", {"instance_id": FAKE_ARG}, id="get_instance"),
        pytest.param("get_instances", {}, id="get_instances"),
        pytest.param("delete_expired_keys", {}, id="delete_expired_keys"),
    ],
)
def test_raises_openstack_error(
    openstack_cloud: OpenstackCloud,
    public_method: str,
    args: dict[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: Mock OpenstackCloud and openstack.connect to raise an Openstack api exception.
    act: Call a public method which connects to Openstack.
    assert: OpenStackError is raised.
    """
    # Mock expanduser as this is used in OpenstackCloud constructor
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.Path.expanduser", MagicMock()
    )

    openstack_connect_mock = MagicMock(spec=openstack.connect)

    excs = (openstack.exceptions.SDKException, keystoneauth1.exceptions.ClientException)
    for exc in excs:
        openstack_connect_mock.side_effect = exc("an exception occurred")
        monkeypatch.setattr(
            "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
            openstack_connect_mock,
        )
        with pytest.raises(OpenStackError) as innerexc:
            getattr(openstack_cloud, public_method)(**args)
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
    arrange: Create an OpenstackSecurityGroup with a list of rules.
    act: Call get_missing_security_rules with possibly extra ports to open.
    assert: If there are missing security rules, they will be returned so they can be added.
    """
    security_group = OpenstackSecurityGroup()
    security_group.security_group_rules = security_rules

    missing = get_missing_security_rules(security_group, extra_ports)
    assert missing == expected_missing_rules


def test_keypair_cleanup_freshly_created_keypairs(
    openstack_cloud: OpenstackCloud, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    arrange: Keypairs with different creation time.
    act: Call cleanup.
    assert: Only keypairs older than a threshold are deleted.
    """
    # arrange #
    # Mock expanduser as this is used in OpenstackCloud constructor
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.Path.expanduser", MagicMock()
    )

    openstack_cloud._ssh_key_dir = tmp_path / "ssh_key_dir"
    openstack_cloud._ssh_key_dir.mkdir()

    openstack_connect_mock = MagicMock(spec=openstack.connect)
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
        openstack_connect_mock,
    )

    now = _mock_datetime_now(monkeypatch)
    keypairs_older_or_same_min_age = (
        (
            openstack_cloud._ssh_key_dir / f"{FAKE_PREFIX}-old-{i}.key",
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
            openstack_cloud._ssh_key_dir / f"{FAKE_PREFIX}-new-{i}.key",
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
                name=keypair.name.removesuffix(".key"),
            )
        )

    openstack_connection_mock = MagicMock(spec=Connection)
    openstack_connection_mock.__enter__.return_value = openstack_connection_mock
    openstack_connection_mock.list_keypairs.return_value = keypair_list
    openstack_connection_mock.list_keypairs.return_value = keypair_list
    openstack_connect_mock.return_value = openstack_connection_mock

    # act #
    openstack_cloud.delete_expired_keys()

    # assert #
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


def test_get_ssh_connection_success(openstack_cloud, monkeypatch):
    """
    arrange: Setup SSH connection to succeed.
    act: Get SSH connection.
    assert: No SSHError raised. No SSH connection errors.
    """
    mock_result = MagicMock(ok=True, stdout=_TEST_STRING)
    mock_connection = MagicMock(run=MagicMock(return_value=mock_result))

    def mock_ssh_connection(*_args, **_kwargs) -> MagicMock:
        """Mock get_ssh_connection function.

        Returns:
            The mocked connection.
        """
        return mock_connection

    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.SSHConnection", mock_ssh_connection
    )

    mock_instance = MagicMock()
    mock_instance.addresses = ["mock_ip"]
    with openstack_cloud.get_ssh_connection(mock_instance) as conn:
        assert conn == mock_connection


def test_get_ssh_connection_failure(openstack_cloud, monkeypatch):
    """
    arrange: Setup SSH connection to fail.
    act: Get SSH connection.
    assert: Error raised with no connectable SSH address found.
    """
    mock_result = MagicMock(ok=False, stdout=_TEST_STRING)
    mock_connection = MagicMock(run=MagicMock(return_value=mock_result))

    def mock_ssh_connection(*_args, **_kwargs) -> MagicMock:
        """Mock get_ssh_connection function.

        Returns:
            The mocked connection.
        """
        return mock_connection

    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.SSHConnection", mock_ssh_connection
    )

    mock_instance = MagicMock()
    mock_instance.addresses = ["mock_ip"]
    with pytest.raises(SSHError) as err:
        with openstack_cloud.get_ssh_connection(mock_instance):
            pass

    assert "No connectable SSH addresses found" in str(err.value)


# We test this internal method because this fails silently without bubbling up exceptions due to
# it's non-critical nature.
def test__delete_keypair_fail(
    openstack_cloud: OpenstackCloud, mock_openstack_conn: MagicMock, caplog: LogCaptureFixture
):
    """
    arrange: given a mocked openstack delete_keypair method that returns False.
    act: when _delete_keypair method is called.
    assert: None is returned and the failure is logged.
    """
    mock_openstack_conn.delete_keypair = MagicMock(return_value=False)
    test_key_instance_id = InstanceID(prefix="test-key-delete", reactive=False, suffix="fail")

    assert (
        openstack_cloud._delete_keypair(
            _DeleteKeypairConfig(
                keys_dir=MagicMock(), instance_id=test_key_instance_id, conn=mock_openstack_conn
            )
        )
        is None
    )
    assert f"Failed to delete key: {test_key_instance_id.name}" in caplog.messages


def test__delete_keypair_error(
    openstack_cloud: OpenstackCloud, mock_openstack_conn: MagicMock, caplog: LogCaptureFixture
):
    """
    arrange: given a mocked openstack delete_keypair method that returns False.
    act: when _delete_keypair method is called.
    assert: None is returned and the failure is logged.
    """
    mock_openstack_conn.delete_keypair = MagicMock(
        side_effect=[openstack.exceptions.ResourceTimeout()]
    )
    test_key_instance_id = InstanceID(prefix="test-key-delete", reactive=False, suffix="fail")

    assert (
        openstack_cloud._delete_keypair(
            _DeleteKeypairConfig(
                keys_dir=MagicMock(), instance_id=test_key_instance_id, conn=mock_openstack_conn
            )
        )
        is None
    )
    assert f"Error attempting to delete key: {test_key_instance_id.name}" in caplog.messages


def test_delete_instances_partial_server_delete_failure(
    monkeypatch: pytest.MonkeyPatch, openstack_cloud: OpenstackCloud, caplog: LogCaptureFixture
):
    """
    arrange: given a mocked openstack connection that errors on few failed requests.
    act: when delete_instances method is called.
    assert: successfully deleted instance IDs are returned and failed instances are logged.
    """
    successful_delete_id = InstanceID(prefix="success", reactive=False, suffix="")
    already_deleted_id = InstanceID(prefix="already_deleted", reactive=False, suffix="")
    timeout_id = InstanceID(prefix="timeout error", reactive=False, suffix="")
    mock_cloud = FakeOpenstackCloud(
        initial_servers=[successful_delete_id, timeout_id],
        server_to_errors={timeout_id: openstack.exceptions.ResourceTimeout()},
    )
    monkeypatch.setattr(
        github_runner_manager.openstack_cloud.openstack_cloud.openstack,
        "connect",
        MagicMock(return_value=mock_cloud),
    )

    deleted_instance_ids = openstack_cloud.delete_instances(
        instance_ids=[successful_delete_id, already_deleted_id, timeout_id]
    )

    assert successful_delete_id in deleted_instance_ids
    assert already_deleted_id not in deleted_instance_ids
    assert timeout_id not in deleted_instance_ids
    assert f"Failed to delete OpenStack VM instance: {timeout_id}" in caplog.messages


def test_delete_instances(
    openstack_cloud: OpenstackCloud,
    mock_openstack_conn: MagicMock,
):
    """
    arrange: given a mocked openstack connection.
    act: when delete_instances method is called.
    assert: deleted instance IDs are returned.
    """
    mock_openstack_conn.delete_server = MagicMock(side_effect=[True, False])
    successful_delete_id = InstanceID(prefix="success", reactive=False, suffix="")
    already_deleted_id = InstanceID(prefix="already_deleted", reactive=False, suffix="")

    deleted_instance_ids = openstack_cloud.delete_instances(
        instance_ids=[successful_delete_id, already_deleted_id]
    )

    assert deleted_instance_ids == [successful_delete_id]


@pytest.mark.parametrize(
    "max_compute_api_version, expected_version",
    [
        pytest.param(
            "2.110",
            _MAX_NOVA_COMPUTE_API_VERSION,
            id="higher version but string is lexically smaller",
        ),
        pytest.param(
            "2.92", _MAX_NOVA_COMPUTE_API_VERSION, id="one higher version than supported"
        ),
        pytest.param("2.91", _MAX_NOVA_COMPUTE_API_VERSION, id="highest supported version"),
        pytest.param("2.90", "2.90", id="one version lower than supported"),
        pytest.param("2.1", "2.1", id="really low version"),
    ],
)
def test_get_openstack_connection_sets_max_compute_api(
    openstack_cloud,
    monkeypatch: pytest.MonkeyPatch,
    max_compute_api_version: str,
    expected_version: str,
):
    """
    arrange: Setup get_compute_api to return different max versions.
    act: Get OpenStack connection using context manager
    assert: The max compute API version is set to be < 2.95.
    """
    monkeypatch.setattr(
        openstack_cloud,
        "_determine_max_compute_api_version_by_cloud",
        MagicMock(return_value=max_compute_api_version),
    )
    openstack_connect_mock = MagicMock()
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
        openstack_connect_mock,
    )

    with openstack_cloud._get_openstack_connection():
        pass

    assert openstack_connect_mock.call_args[1]["compute_api_version"] == expected_version


def test_determine_max_api_version(
    openstack_cloud: OpenstackCloud, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Mock the OpenStack connection to return a specific max API version.
    act: Call _determine_max_compute_api_version.
    assert: The returned version is as expected.
    """
    mock_connection = MagicMock()
    monkeypatch.setattr(
        "github_runner_manager.openstack_cloud.openstack_cloud.openstack.connect",
        MagicMock(return_value=mock_connection),
    )
    mock_connection.__enter__.return_value = mock_connection

    endpoint_resp_json = {
        "version": {
            "id": "v2.1",
            "status": "CURRENT",
            "version": "2.96",
            "min_version": "2.1",
            "updated": "2013-07-23T11:33:21Z",
            "links": [
                {"rel": "self", "href": "http://172.16.1.204/openstack-nova/v2.1/"},
                {"rel": "describedby", "type": "text/html", "href": "http://docs.openstack.org/"},
            ],
            "media-types": [
                {
                    "base": "application/json",
                    "type": "application/vnd.openstack.compute+json;version=2.1",
                }
            ],
        }
    }
    endpoint_resp = MagicMock()
    endpoint_resp.json.return_value = endpoint_resp_json

    session_mock = MagicMock()
    mock_connection.session = session_mock
    session_mock.get = MagicMock(return_value=endpoint_resp)

    max_version = openstack_cloud._determine_max_compute_api_version_by_cloud()
    assert max_version == "2.96"
