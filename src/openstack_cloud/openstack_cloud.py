# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for accessing OpenStack API for managing servers."""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Iterable, Iterator, cast

import openstack
import openstack.exceptions
import paramiko
import yaml
from fabric import Connection as SSHConnection
from openstack.compute.v2.keypair import Keypair as OpenstackKeypair
from openstack.compute.v2.server import Server as OpenstackServer
from openstack.connection import Connection as OpenstackConnection
from openstack.network.v2.security_group import SecurityGroup as OpenstackSecurityGroup
from paramiko.ssh_exception import NoValidConnectionsError

from errors import KeyfileError, OpenStackError, SSHError
from utilities import retry

logger = logging.getLogger(__name__)

_CLOUDS_YAML_PATH = Path.home() / ".config/openstack/clouds.yaml"

# Update the version when the security group rules are not backward compatible.
_SECURITY_GROUP_NAME = "github-runner-v1"

_CREATE_SERVER_TIMEOUT = 5 * 60
_SSH_TIMEOUT = 30
_SSH_KEY_PATH = Path("/home/ubuntu/.ssh")
_TEST_STRING = "test_string"


@dataclass
class OpenstackInstance:
    """Represents an OpenStack instance.

    Attributes:
        server_id: ID of server assigned by OpenStack.
        server_name: Name of the server on OpenStack.
        instance_id: ID used by OpenstackCloud class to manage the instances. See docs on the
            OpenstackCloud.
        addresses: IP addresses assigned to the server.
        status: Status of the server.
    """

    server_id: str
    server_name: str
    instance_id: str
    addresses: list[str]
    status: str

    def __init__(self, server: OpenstackServer, prefix: str):
        """Construct the object.

        Args:
            server: The OpenStack server.
            prefix: The name prefix for the servers.

        Raises:
            ValueError: Provided server should not be managed under this prefix.
        """
        self.server_id = server.id
        self.server_name = server.name
        self.status = server.status
        self.addresses = [
            address["addr"]
            for network_addresses in server.addresses.values()
            for address in network_addresses
        ]

        if not self.server_name.startswith(f"{prefix}-"):
            # Should never happen.
            raise ValueError(
                f"Found openstack server {server.name} managed under prefix {prefix}, contact devs"
            )
        self.instance_id = self.server_name[len(prefix) + 1 :]


@contextmanager
@retry(tries=2, delay=5, local_logger=logger)
def _get_openstack_connection(
    clouds_config: dict[str, dict], cloud: str
) -> Iterator[OpenstackConnection]:
    """Create a connection context managed object, to be used within with statements.

    The file of _CLOUDS_YAML_PATH should only be modified by this function.

    Args:
        clouds_config: The configuration in clouds.yaml format to apply.
        cloud: The name of cloud to use in the clouds.yaml.

    Raises:
        OpenStackError: if the credentials provided is not authorized.

    Yields:
        An openstack.connection.Connection object.
    """
    if not _CLOUDS_YAML_PATH.exists():
        _CLOUDS_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Concurrency: Very small chance for the file to be corrupted due to multiple process calling
    # this function and writing the file at the same time. This should cause the `conn.authorize`
    # to fail, and retry of this function would resolve this.
    _CLOUDS_YAML_PATH.write_text(data=yaml.dump(clouds_config), encoding="utf-8")

    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. Therefore, no catch here for such exception.
    try:
        with openstack.connect(cloud=cloud) as conn:
            conn.authorize()
            yield conn
    # pylint thinks this isn't an exception, but does inherit from Exception class.
    except openstack.exceptions.HttpException as exc:  # pylint: disable=bad-exception-cause
        logger.exception("OpenStack API call failure")
        raise OpenStackError("Failed OpenStack API call") from exc


class OpenstackCloud:
    """Client to interact with OpenStack cloud.

    The OpenStack server name is managed by this cloud. Caller refers to the instances via
    instance_id. If the caller needs the server name, e.g., for logging, it can be queried with
    get_server_name.
    """

    def __init__(self, clouds_config: dict[str, dict], cloud: str, prefix: str):
        """Create the object.

        Args:
            clouds_config: The openstack clouds.yaml in dict format.
            cloud: The name of cloud to use in the clouds.yaml.
            prefix: Prefix attached to names of resource managed by this instance. Used for
                identifying which resource belongs to this instance.
        """
        self._clouds_config = clouds_config
        self._cloud = cloud
        self.prefix = prefix

    # Ignore "Too many arguments" as 6 args should be fine. Move to a dataclass if new args are
    # added.
    def launch_instance(  # pylint: disable=R0913
        self, instance_id: str, image: str, flavor: str, network: str, cloud_init: str
    ) -> OpenstackInstance:
        """Create an OpenStack instance.

        Args:
            instance_id: The instance ID to form the instance name.
            image: The image used to create the instance.
            flavor: The flavor used to create the instance.
            network: The network used to create the instance.
            cloud_init: The cloud init userdata to startup the instance.

        Raises:
            OpenStackError: Unable to create OpenStack server.

        Returns:
            The OpenStack instance created.
        """
        full_name = self.get_server_name(instance_id)
        logger.info("Creating openstack server with %s", full_name)

        with _get_openstack_connection(
            clouds_config=self._clouds_config, cloud=self._cloud
        ) as conn:
            security_group = OpenstackCloud._ensure_security_group(conn)
            keypair = OpenstackCloud._setup_keypair(conn, full_name)

            try:
                server = conn.create_server(
                    name=full_name,
                    image=image,
                    key_name=keypair.name,
                    flavor=flavor,
                    network=network,
                    security_groups=[security_group.id],
                    userdata=cloud_init,
                    auto_ip=False,
                    timeout=_CREATE_SERVER_TIMEOUT,
                    wait=True,
                )
            except openstack.exceptions.ResourceTimeout as err:
                logger.exception("Timeout creating openstack server %s", full_name)
                logger.info(
                    "Attempting clean up of openstack server %s that timeout during creation",
                    full_name,
                )
                self._delete_instance(conn, full_name)
                raise OpenStackError(f"Timeout creating openstack server {full_name}") from err
            except openstack.exceptions.SDKException as err:
                logger.exception("Failed to create openstack server %s", full_name)
                self._delete_keypair(conn, instance_id)
                raise OpenStackError(f"Failed to create openstack server {full_name}") from err

            return OpenstackInstance(server, self.prefix)

    def get_instance(self, instance_id: str) -> OpenstackInstance | None:
        """Get OpenStack instance by instance ID.

        Args:
            instance_id: The instance ID.

        Returns:
            The OpenStack instance if found.
        """
        full_name = self.get_server_name(instance_id)
        logger.info("Getting openstack server with %s", full_name)

        with _get_openstack_connection(
            clouds_config=self._clouds_config, cloud=self._cloud
        ) as conn:
            server = OpenstackCloud._get_and_ensure_unique_server(conn, full_name)
            if server is not None:
                return OpenstackInstance(server, self.prefix)
        return None

    def delete_instance(self, instance_id: str) -> None:
        """Delete a openstack instance.

        Args:
            instance_id: The instance ID of the instance to delete.
        """
        full_name = self.get_server_name(instance_id)
        logger.info("Deleting openstack server with %s", full_name)

        with _get_openstack_connection(
            clouds_config=self._clouds_config, cloud=self._cloud
        ) as conn:
            self._delete_instance(conn, full_name)

    def _delete_instance(self, conn: OpenstackConnection, full_name: str) -> None:
        """Delete a openstack instance.

        Raises:
            OpenStackError: Unable to delete OpenStack server.

        Args:
            conn: The openstack connection to use.
            full_name: The full name of the server.
        """
        try:
            server = OpenstackCloud._get_and_ensure_unique_server(conn, full_name)
            if server is not None:
                conn.delete_server(name_or_id=server.id)
            OpenstackCloud._delete_keypair(conn, full_name)
        except (
            openstack.exceptions.SDKException,
            openstack.exceptions.ResourceTimeout,
        ) as err:
            raise OpenStackError(f"Failed to remove openstack runner {full_name}") from err

    def get_ssh_connection(self, instance: OpenstackInstance) -> SSHConnection:
        """Get SSH connection to an OpenStack instance.

        Args:
            instance: The OpenStack instance to connect to.

        Raises:
            SSHError: Unable to get a working SSH connection to the instance.
            KeyfileError: Unable to find the keyfile to connect to the instance.

        Returns:
            SSH connection object.
        """
        key_path = OpenstackCloud._get_key_path(instance.server_name)

        if not key_path.exists():
            raise KeyfileError(
                f"Missing keyfile for server: {instance.server_name}, key path: {key_path}"
            )
        if not instance.addresses:
            raise SSHError(f"No addresses found for OpenStack server {instance.server_name}")

        for ip in instance.addresses:
            try:
                connection = SSHConnection(
                    host=ip,
                    user="ubuntu",
                    connect_kwargs={"key_filename": str(key_path)},
                    connect_timeout=_SSH_TIMEOUT,
                )
                result = connection.run(f"echo {_TEST_STRING}", warn=True, timeout=_SSH_TIMEOUT)
                if not result.ok:
                    logger.warning(
                        "SSH test connection failed, server: %s, address: %s",
                        instance.server_name,
                        ip,
                    )
                    continue
                if _TEST_STRING in result.stdout:
                    return connection
            except (NoValidConnectionsError, TimeoutError, paramiko.ssh_exception.SSHException):
                logger.warning(
                    "Unable to SSH into %s with address %s",
                    instance.server_name,
                    connection.host,
                    exc_info=True,
                )
                continue
        raise SSHError(
            f"No connectable SSH addresses found, server: {instance.server_name}, "
            f"addresses: {instance.addresses}"
        )

    def get_instances(self) -> tuple[OpenstackInstance, ...]:
        """Get all OpenStack instances.

        Returns:
            The OpenStack instances.
        """
        logger.info("Getting all openstack servers managed by the charm")

        with _get_openstack_connection(
            clouds_config=self._clouds_config, cloud=self._cloud
        ) as conn:
            instance_list = self._get_openstack_instances(conn)
            server_names = set(server.name for server in instance_list)

            server_list = [
                OpenstackCloud._get_and_ensure_unique_server(conn, name) for name in server_names
            ]
            return tuple(
                OpenstackInstance(server, self.prefix)
                for server in server_list
                if server is not None
            )

    def cleanup(self) -> None:
        """Cleanup unused key files and openstack keypairs."""
        with _get_openstack_connection(
            clouds_config=self._clouds_config, cloud=self._cloud
        ) as conn:
            instances = self._get_openstack_instances(conn)
            exclude_list = [server.name for server in instances]
            self._cleanup_key_files(exclude_list)
            self._cleanup_openstack_keypairs(conn, exclude_list)

    def get_server_name(self, instance_id: str) -> str:
        """Get server name on OpenStack.

        Args:
            instance_id: ID used to identify a instance.

        Returns:
            The OpenStack server name.
        """
        return f"{self.prefix}-{instance_id}"

    def _cleanup_key_files(self, exclude_instances: Iterable[str]) -> None:
        """Delete all SSH key files except the specified instances.

        Args:
            exclude_instances: The keys of these instance will not be deleted.
        """
        logger.info("Cleaning up SSH key files")
        exclude_filename = set(
            OpenstackCloud._get_key_path(instance) for instance in exclude_instances
        )

        total = 0
        deleted = 0
        for path in _SSH_KEY_PATH.iterdir():
            # Find key file from this application.
            if path.is_file() and path.name.startswith(self.prefix) and path.name.endswith(".key"):
                total += 1
                if path in exclude_filename:
                    continue
                path.unlink()
                deleted += 1
        logger.info("Found %s key files, clean up %s key files", total, deleted)

    def _cleanup_openstack_keypairs(
        self, conn: OpenstackConnection, exclude_instances: Iterable[str]
    ) -> None:
        """Delete all OpenStack keypairs except the specified instances.

        Args:
            conn: The Openstack connection instance.
            exclude_instances: The keys of these instance will not be deleted.
        """
        logger.info("Cleaning up openstack keypairs")
        exclude_instance_set = set(exclude_instances)
        keypairs = conn.list_keypairs()
        for key in keypairs:
            # The `name` attribute is of resource.Body type.
            if key.name and str(key.name).startswith(self.prefix):
                if str(key.name) in exclude_instance_set:
                    continue
                try:
                    self._delete_keypair(conn, key.name)
                except openstack.exceptions.SDKException:
                    logger.warning(
                        "Unable to delete OpenStack keypair associated with deleted key file %s ",
                        key.name,
                    )

    def _get_openstack_instances(self, conn: OpenstackConnection) -> tuple[OpenstackServer, ...]:
        """Get the OpenStack servers managed by this unit.

        Args:
            conn: The connection object to access OpenStack cloud.

        Returns:
            List of OpenStack instances.
        """
        return tuple(
            server
            for server in cast(list[OpenstackServer], conn.list_servers())
            if server.name.startswith(f"{self.prefix}-")
        )

    @staticmethod
    def _get_and_ensure_unique_server(
        conn: OpenstackConnection, name: str
    ) -> OpenstackServer | None:
        """Get the latest server of the name and ensure it is unique.

        If multiple servers with the same name are found, the latest server in creation time is
        returned. Other servers is deleted.

        Args:
            conn: The connection to OpenStack.
            name: The name of the OpenStack name.

        Returns:
            A server with the name.
        """
        servers: list[OpenstackServer] = conn.search_servers(name)

        if not servers:
            return None

        # 2024/08/14: The `format` arg for `strptime` is the default format.
        # This is only provided to get around a bug of the function with type checking.
        latest_server = reduce(
            lambda a, b: (
                a
                if datetime.strptime(a.created_at, "a %b %d %H:%M:%S %Y")
                < datetime.strptime(b.create_at, "a %b %d %H:%M:%S %Y")
                else b
            ),
            servers,
        )
        outdated_servers = filter(lambda x: x != latest_server, servers)
        for server in outdated_servers:
            try:
                conn.delete_server(name_or_id=server.id)
            except (openstack.exceptions.SDKException, openstack.exceptions.ResourceTimeout):
                logger.warning(
                    "Unable to delete server with duplicate name %s with ID %s",
                    name,
                    server.id,
                    stack_info=True,
                )

        return latest_server

    @staticmethod
    def _get_key_path(name: str) -> Path:
        """Get the filepath for storing private SSH of a runner.

        Args:
            name: The name of the runner.

        Returns:
            Path to reserved for the key file of the runner.
        """
        return _SSH_KEY_PATH / f"{name}.key"

    @staticmethod
    def _setup_keypair(conn: OpenstackConnection, name: str) -> OpenstackKeypair:
        """Create OpenStack keypair.

        Args:
            conn: The connection object to access OpenStack cloud.
            name: The name of the keypair.

        Returns:
            The OpenStack keypair.
        """
        key_path = OpenstackCloud._get_key_path(name)

        if key_path.exists():
            logger.warning("Existing private key file for %s found, removing it.", name)
            key_path.unlink(missing_ok=True)

        keypair = conn.create_keypair(name=name)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(keypair.private_key)
        key_path.chmod(0o400)
        return keypair

    @staticmethod
    def _delete_keypair(conn: OpenstackConnection, name: str) -> None:
        """Delete OpenStack keypair.

        Args:
            conn: The connection object to access OpenStack cloud.
            name: The name of the keypair.
        """
        try:
            # Keypair have unique names, access by ID is not needed.
            if not conn.delete_keypair(name):
                logger.warning("Unable to delete keypair for %s", name)
        except (openstack.exceptions.SDKException, openstack.exceptions.ResourceTimeout):
            logger.warning("Unable to delete keypair for %s", name, stack_info=True)

        key_path = OpenstackCloud._get_key_path(name)
        key_path.unlink(missing_ok=True)

    @staticmethod
    def _ensure_security_group(conn: OpenstackConnection) -> OpenstackSecurityGroup:
        """Ensure runner security group exists.

        Args:
            conn: The connection object to access OpenStack cloud.

        Returns:
            The security group with the rules for runners.
        """
        rule_exists_icmp = False
        rule_exists_ssh = False
        rule_exists_tmate_ssh = False

        security_group_list = conn.list_security_groups(filters={"name": _SECURITY_GROUP_NAME})
        # Pick the first security_group returned.
        security_group = next(iter(security_group_list), None)
        if security_group is None:
            logger.info("Security group %s not found, creating it", _SECURITY_GROUP_NAME)
            security_group = conn.create_security_group(
                name=_SECURITY_GROUP_NAME,
                description="For servers managed by the github-runner charm.",
            )
        else:
            existing_rules = security_group.security_group_rules
            for rule in existing_rules:
                if rule["protocol"] == "icmp":
                    logger.debug(
                        "Found ICMP rule in existing security group %s of ID %s",
                        _SECURITY_GROUP_NAME,
                        security_group.id,
                    )
                    rule_exists_icmp = True
                if (
                    rule["protocol"] == "tcp"
                    and rule["port_range_min"] == rule["port_range_max"] == 22
                ):
                    logger.debug(
                        "Found SSH rule in existing security group %s of ID %s",
                        _SECURITY_GROUP_NAME,
                        security_group.id,
                    )
                    rule_exists_ssh = True
                if (
                    rule["protocol"] == "tcp"
                    and rule["port_range_min"] == rule["port_range_max"] == 10022
                ):
                    logger.debug(
                        "Found tmate SSH rule in existing security group %s of ID %s",
                        _SECURITY_GROUP_NAME,
                        security_group.id,
                    )
                    rule_exists_tmate_ssh = True

        if not rule_exists_icmp:
            conn.create_security_group_rule(
                secgroup_name_or_id=security_group.id,
                protocol="icmp",
                direction="ingress",
                ethertype="IPv4",
            )
        if not rule_exists_ssh:
            conn.create_security_group_rule(
                secgroup_name_or_id=security_group.id,
                port_range_min="22",
                port_range_max="22",
                protocol="tcp",
                direction="ingress",
                ethertype="IPv4",
            )
        if not rule_exists_tmate_ssh:
            conn.create_security_group_rule(
                secgroup_name_or_id=security_group.id,
                port_range_min="10022",
                port_range_max="10022",
                protocol="tcp",
                direction="egress",
                ethertype="IPv4",
            )
        return security_group
