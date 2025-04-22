# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for accessing OpenStack API for managing servers."""
import copy
import functools
import logging
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, ParamSpec, TypeVar, cast

import keystoneauth1.exceptions
import openstack
import openstack.exceptions
import paramiko
from fabric import Connection as SSHConnection
from openstack.compute.v2.keypair import Keypair as OpenstackKeypair
from openstack.compute.v2.server import Server as OpenstackServer
from openstack.connection import Connection as OpenstackConnection
from openstack.network.v2.security_group import SecurityGroup as OpenstackSecurityGroup
from openstack.network.v2.security_group_rule import SecurityGroupRule
from paramiko.ssh_exception import NoValidConnectionsError

from github_runner_manager.errors import KeyfileError, OpenStackError, SSHError
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.openstack_cloud.configuration import OpenStackCredentials
from github_runner_manager.openstack_cloud.constants import CREATE_SERVER_TIMEOUT
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig

logger = logging.getLogger(__name__)

# Update the version when the security group rules are not backward compatible.
_SECURITY_GROUP_NAME = "github-runner-v1"

_SSH_TIMEOUT = 30
_TEST_STRING = "test_string"

SecurityRuleDict = dict[str, Any]

DEFAULT_SECURITY_RULES: dict[str, SecurityRuleDict] = {
    "icmp": {
        "protocol": "icmp",
        "direction": "ingress",
        "ethertype": "IPv4",
    },
    "ssh": {
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "direction": "ingress",
        "ethertype": "IPv4",
    },
    "tmate_ssh": {
        "protocol": "tcp",
        "port_range_min": 10022,
        "port_range_max": 10022,
        "direction": "egress",
        "ethertype": "IPv4",
    },
}

# Keypairs younger than this value should not be deleted to avoid a race condition where
# the openstack server is in construction but not yet returned by the API, and the keypair gets
# deleted.
_MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION = 60


@dataclass
class OpenstackInstance:
    """Represents an OpenStack instance.

    Attributes:
        addresses: IP addresses assigned to the server.
        created_at: The timestamp in which the instance was created at.
        instance_id: ID used by OpenstackCloud class to manage the instances. See docs on the
            OpenstackCloud.
        server_id: ID of server assigned by OpenStack.
        status: Status of the server.
        metadata: Medatada of the server.
    """

    addresses: list[str]
    created_at: datetime
    instance_id: InstanceID
    server_id: str
    status: str
    metadata: RunnerMetadata

    def __init__(self, server: OpenstackServer, prefix: str):
        """Construct the object.

        Args:
            server: The OpenStack server.
            prefix: The name prefix for the servers.
        """
        self.addresses = [
            address["addr"]
            for network_addresses in server.addresses.values()
            for address in network_addresses
        ]
        self.created_at = datetime.strptime(server.created_at, "%Y-%m-%dT%H:%M:%SZ")
        self.instance_id = InstanceID.build_from_name(prefix, server.name)
        self.server_id = server.id
        self.status = server.status
        # To be backwards compatible, we need a default RunnerMetadata.
        self.metadata = RunnerMetadata(**server.metadata) if server.metadata else RunnerMetadata()


P = ParamSpec("P")
T = TypeVar("T")


def _catch_openstack_errors(func: Callable[P, T]) -> Callable[P, T]:
    """Decorate a function to wrap OpenStack exceptions in a custom exception.

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.
    """

    @functools.wraps(func)
    def exception_handling_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        """Wrap the function with exception handling.

        Args:
            args: The positional arguments.
            kwargs: The keyword arguments.

        Raises:
            OpenStackError: If any OpenStack exception is caught.

        Returns:
            The return value of the decorated function.
        """
        try:
            return func(*args, **kwargs)
        except (
            openstack.exceptions.SDKException,
            keystoneauth1.exceptions.ClientException,
        ) as exc:
            logger.error("OpenStack API call failure")
            raise OpenStackError("Failed OpenStack API call") from exc

    return exception_handling_wrapper


@contextmanager
def _get_openstack_connection(credentials: OpenStackCredentials) -> Iterator[OpenstackConnection]:
    """Create a connection context managed object, to be used within with statements.

    Using the context manager ensures that the connection is properly closed after use.

    Args:
        credentials: The OpenStack authorization information.

    Yields:
        An openstack.connection.Connection object.
    """
    # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
    # I could not reproduce it. Therefore, no catch here for such exception.
    with openstack.connect(
        auth_url=credentials.auth_url,
        project_name=credentials.project_name,
        username=credentials.username,
        password=credentials.password,
        region_name=credentials.region_name,
        user_domain_name=credentials.user_domain_name,
        project_domain_name=credentials.project_domain_name,
    ) as conn:
        conn.authorize()
        yield conn


class OpenstackCloud:
    """Client to interact with OpenStack cloud.

    The OpenStack server name is managed by this cloud. Caller refers to the instances via
    instance_id. It is the same as the server name.
    """

    def __init__(
        self,
        credentials: OpenStackCredentials,
        prefix: str,
        system_user: str,
        proxy_command: str | None = None,
    ):
        """Create the object.

        Args:
            credentials: The OpenStack authorization information.
            prefix: Prefix attached to names of resource managed by this instance. Used for
                identifying which resource belongs to this instance.
            system_user: The system user to own the key files.
            proxy_command: The gateway argument for fabric Connection. Similar to ProxyCommand in
                ssh-config.
        """
        self._credentials = credentials
        self.prefix = prefix
        self._system_user = system_user
        self._ssh_key_dir = Path(f"~{system_user}").expanduser() / ".ssh"
        self._proxy_command = proxy_command

    @_catch_openstack_errors
    # Pending to review the list of arguments
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def launch_instance(
        self,
        *,
        metadata: RunnerMetadata,
        instance_id: InstanceID,
        server_config: OpenStackServerConfig,
        cloud_init: str,
        ingress_tcp_ports: list[int] | None = None,
    ) -> OpenstackInstance:
        """Create an OpenStack instance.

        Args:
            metadata: Metadata for the runner.
            instance_id: The instance ID to form the instance name.
            server_config: Configuration for the instance to create.
            cloud_init: The cloud init userdata to startup the instance.
            ingress_tcp_ports: Ports to be allowed to connect to the new instance.

        Raises:
            OpenStackError: Unable to create OpenStack server.

        Returns:
            The OpenStack instance created.
        """
        logger.info("Creating openstack server with %s", instance_id)

        with _get_openstack_connection(credentials=self._credentials) as conn:
            security_group = OpenstackCloud._ensure_security_group(conn, ingress_tcp_ports)
            keypair = self._setup_keypair(conn, instance_id)
            meta = metadata.as_dict()
            meta["prefix"] = self.prefix
            try:
                server = conn.create_server(
                    name=instance_id.name,
                    image=server_config.image,
                    key_name=keypair.name,
                    flavor=server_config.flavor,
                    network=server_config.network,
                    security_groups=[security_group.id],
                    userdata=cloud_init,
                    auto_ip=False,
                    timeout=CREATE_SERVER_TIMEOUT,
                    wait=True,
                    meta=meta,
                )
            except openstack.exceptions.ResourceTimeout as err:
                logger.exception("Timeout creating openstack server %s", instance_id)
                logger.info(
                    "Attempting clean up of openstack server %s that timeout during creation",
                    instance_id,
                )
                self._delete_instance(conn, instance_id)
                raise OpenStackError(f"Timeout creating openstack server {instance_id}") from err
            except openstack.exceptions.SDKException as err:
                logger.exception("Failed to create openstack server %s", instance_id)
                self._delete_keypair(conn, instance_id)
                raise OpenStackError(f"Failed to create openstack server {instance_id}") from err

            return OpenstackInstance(server, self.prefix)

    @_catch_openstack_errors
    def get_instance(self, instance_id: InstanceID) -> OpenstackInstance | None:
        """Get OpenStack instance by instance ID.

        Args:
            instance_id: The instance ID.

        Returns:
            The OpenStack instance if found.
        """
        logger.info("Getting openstack server with %s", instance_id)

        with _get_openstack_connection(credentials=self._credentials) as conn:
            server = OpenstackCloud._get_and_ensure_unique_server(conn, instance_id)
            if server is not None:
                return OpenstackInstance(server, self.prefix)
        return None

    @_catch_openstack_errors
    def delete_instance(self, instance_id: InstanceID) -> None:
        """Delete a openstack instance.

        Args:
            instance_id: The instance ID of the instance to delete.
        """
        logger.info("Deleting openstack server with %s", instance_id)

        with _get_openstack_connection(credentials=self._credentials) as conn:
            self._delete_instance(conn, instance_id)

    def _delete_instance(self, conn: OpenstackConnection, instance_id: InstanceID) -> None:
        """Delete a openstack instance.

        Raises:
            OpenStackError: Unable to delete OpenStack server.

        Args:
            conn: The openstack connection to use.
            instance_id: The full name of the server.
        """
        try:
            server = OpenstackCloud._get_and_ensure_unique_server(conn, instance_id)
            if server is not None:
                conn.delete_server(name_or_id=server.id)
            self._delete_keypair(conn, instance_id)
        except (
            openstack.exceptions.SDKException,
            openstack.exceptions.ResourceTimeout,
        ) as err:
            raise OpenStackError(f"Failed to remove openstack runner {instance_id}") from err

    @_catch_openstack_errors
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
        key_path = self._get_key_path(instance.instance_id.name)

        if not key_path.exists():
            raise KeyfileError(
                f"Missing keyfile for server: {instance.instance_id.name}, key path: {key_path}"
            )
        if not instance.addresses:
            raise SSHError(f"No addresses found for OpenStack server {instance.instance_id.name}")

        for ip in instance.addresses:
            try:
                connection = SSHConnection(
                    host=ip,
                    user="ubuntu",
                    connect_kwargs={"key_filename": str(key_path)},
                    connect_timeout=_SSH_TIMEOUT,
                    gateway=self._proxy_command,
                )
                result = connection.run(
                    f"echo {_TEST_STRING}", warn=True, timeout=_SSH_TIMEOUT, hide=True
                )
                if not result.ok:
                    logger.warning(
                        "SSH test connection failed, server: %s, address: %s",
                        instance.instance_id.name,
                        ip,
                    )
                    continue
                if _TEST_STRING in result.stdout:
                    return connection
            except NoValidConnectionsError as exc:
                logger.warning(
                    "NoValidConnectionsError. Unable to SSH into %s with address %s. Error: %s",
                    instance.instance_id.name,
                    connection.host,
                    str(exc),
                )
                continue
            except (TimeoutError, paramiko.ssh_exception.SSHException):
                logger.warning(
                    "Unable to SSH into %s with address %s",
                    instance.instance_id.name,
                    connection.host,
                    exc_info=True,
                )
                continue
        raise SSHError(
            f"No connectable SSH addresses found, server: {instance.instance_id.name}, "
            f"addresses: {instance.addresses}"
        )

    @_catch_openstack_errors
    def get_instances(self) -> tuple[OpenstackInstance, ...]:
        """Get all OpenStack instances.

        Returns:
            The OpenStack instances.
        """
        logger.info("Getting all openstack servers managed by the charm")

        with _get_openstack_connection(credentials=self._credentials) as conn:
            instance_list = list(self._get_openstack_instances(conn))
            server_names = set(server.name for server in instance_list)

            server_list = [
                OpenstackCloud._get_and_ensure_unique_server(conn, name, instance_list)
                for name in server_names
            ]
            return tuple(
                OpenstackInstance(server, self.prefix)
                for server in server_list
                if server is not None
            )

    @_catch_openstack_errors
    def cleanup(self) -> None:
        """Cleanup unused key files and openstack keypairs."""
        with _get_openstack_connection(credentials=self._credentials) as conn:
            instances = self._get_openstack_instances(conn)
            exclude_keyfiles_set = {
                self._get_key_path(InstanceID.build_from_name(self.prefix, server.name))
                for server in instances
            }
            exclude_keyfiles_set |= set(self._get_fresh_keypair_files())
            self._cleanup_key_files(exclude_keyfiles_set)
            # we implicitly assume that the mapping keyfile -> openstack key name
            # is done using the filename
            exclude_key_set = set(
                keyfile.name.removesuffix(".key") for keyfile in exclude_keyfiles_set
            )
            self._cleanup_openstack_keypairs(conn, exclude_key_set)

    def _get_fresh_keypair_files(self) -> Iterable[Path]:
        """Get the keypair files that are younger than the minimum age."""
        now_ts = datetime.now(timezone.utc).timestamp()
        for path in self._ssh_key_dir.iterdir():
            if (
                path.is_file()
                and InstanceID.name_has_prefix(self.prefix, path.name)
                and path.name.endswith(".key")
                and path.stat().st_mtime >= now_ts - _MIN_KEYPAIR_AGE_IN_SECONDS_BEFORE_DELETION
            ):
                yield path

    def _cleanup_key_files(self, exclude_key_files: set[Path]) -> None:
        """Delete all SSH key files except the specified instances or the ones with young age.

        Args:
            exclude_key_files: These key files will not be deleted.
        """
        logger.info("Cleaning up SSH key files")

        total = 0
        deleted = 0
        for path in self._ssh_key_dir.iterdir():
            # Find key file from this application.
            if (
                path.is_file()
                and InstanceID.name_has_prefix(self.prefix, path.name)
                and path.name.endswith(".key")
            ):
                total += 1
                if path in exclude_key_files:
                    continue
                path.unlink()
                deleted += 1
        logger.info("Found %s key files, clean up %s key files", total, deleted)

    def _cleanup_openstack_keypairs(
        self, conn: OpenstackConnection, exclude_keys: set[str]
    ) -> None:
        """Delete all OpenStack keypairs except the specified instances or the ones with young age.

        Args:
            conn: The Openstack connection instance.
            exclude_keys: These keys will not be deleted.
        """
        logger.info("Cleaning up openstack keypairs")
        keypairs = conn.list_keypairs()
        for key in keypairs:
            # The `name` attribute is of resource.Body type.
            if key.name and InstanceID.name_has_prefix(self.prefix, key.name):
                if str(key.name) in exclude_keys:
                    continue
                try:
                    self._delete_keypair(conn, InstanceID.build_from_name(self.prefix, key.name))
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
            if InstanceID.name_has_prefix(self.prefix, server.name)
        )

    @staticmethod
    def _get_and_ensure_unique_server(
        conn: OpenstackConnection, name: str, all_servers: list[OpenstackServer] | None = None
    ) -> OpenstackServer | None:
        """Get the latest server of the name and ensure it is unique.

        If multiple servers with the same name are found, the latest server in creation time is
        returned. Other servers is deleted.

        Args:
            conn: The connection to OpenStack.
            name: The name of the OpenStack name.
            all_servers: Optionally the list of servers to not request it to openstack again.

        Returns:
            A server with the name.
        """
        servers: list[OpenstackServer]
        if not all_servers:
            servers = conn.search_servers(name)
        else:
            servers = [server for server in all_servers if server.name == name]

        if not servers:
            return None

        latest_server = reduce(
            lambda a, b: (
                a
                if datetime.fromisoformat(a.created_at.replace("Z", "+00:00"))
                < datetime.fromisoformat(b.created_at.replace("Z", "+00:00"))
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

    def _get_key_path(self, instance_id: InstanceID) -> Path:
        """Get the filepath for storing private SSH of a runner.

        Args:
            instance_id: The name of the runner.

        Returns:
            Path to reserved for the key file of the runner.
        """
        return self._ssh_key_dir / f"{instance_id}.key"

    def _setup_keypair(
        self, conn: OpenstackConnection, instance_id: InstanceID
    ) -> OpenstackKeypair:
        """Create OpenStack keypair.

        Args:
            conn: The connection object to access OpenStack cloud.
            instance_id: The name of the keypair.

        Returns:
            The OpenStack keypair.
        """
        key_path = self._get_key_path(instance_id)

        if key_path.exists():
            logger.warning("Existing private key file for %s found, removing it.", instance_id)
            key_path.unlink(missing_ok=True)

        keypair = conn.create_keypair(name=str(instance_id))
        key_path.write_text(keypair.private_key)
        # the charm executes this as root, so we need to change the ownership of the key file
        shutil.chown(key_path, user=self._system_user)
        key_path.chmod(0o400)
        return keypair

    def _delete_keypair(self, conn: OpenstackConnection, instance_id: InstanceID) -> None:
        """Delete OpenStack keypair.

        Args:
            conn: The connection object to access OpenStack cloud.
            instance_id: The name of the keypair.
        """
        logger.debug("Deleting keypair for %s", instance_id)
        try:
            # Keypair have unique names, access by ID is not needed.
            if not conn.delete_keypair(instance_id.name):
                logger.warning("Unable to delete keypair for %s", instance_id)
        except (openstack.exceptions.SDKException, openstack.exceptions.ResourceTimeout):
            logger.warning("Unable to delete keypair for %s", instance_id, stack_info=True)

        key_path = self._get_key_path(instance_id.name)
        key_path.unlink(missing_ok=True)

    @staticmethod
    def _ensure_security_group(
        conn: OpenstackConnection, ingress_tcp_ports: list[int] | None
    ) -> OpenstackSecurityGroup:
        """Ensure runner security group exists.

        These rules will apply to all runners in the security group in
        the OpenStack project. An improvement would be to do it based on
        runner manager and platform provider, as those opened ports will be
        currently for all runners in the openstack project.

        Args:
            conn: The connection object to access OpenStack cloud.
            ingress_tcp_ports: Ports to create an ingress rule for.

        Returns:
            The security group with the rules for runners.
        """
        security_group_list = conn.list_security_groups(filters={"name": _SECURITY_GROUP_NAME})
        # Pick the first security_group returned.
        security_group = next(iter(security_group_list), None)
        if security_group is None:
            logger.info("Security group %s not found, creating it", _SECURITY_GROUP_NAME)
            security_group = conn.create_security_group(
                name=_SECURITY_GROUP_NAME,
                description="For servers managed by the github-runner charm.",
            )

        missing_rules = get_missing_security_rules(security_group, ingress_tcp_ports)

        for missing_rule_name, missing_rule in missing_rules.items():
            conn.create_security_group_rule(secgroup_name_or_id=security_group.id, **missing_rule)
            logger.info(
                "Adding %s in existing security group %s of ID %s",
                missing_rule_name,
                _SECURITY_GROUP_NAME,
                security_group.id,
            )
        return security_group


def get_missing_security_rules(
    security_group: OpenstackSecurityGroup, ingress_tcp_ports: list[int] | None
) -> dict[str, SecurityRuleDict]:
    """Get security rules to add to the security group.

    Args:
        security_group: The security group where rules will be added.
        ingress_tcp_ports: Ports to create an ingress rule for.

    Returns:
        A dictionary with the rules that should be added to the security group.
    """
    missing_rules: dict[str, SecurityRuleDict] = {}

    # We do not want to mess with the default security rules, so the deepcopy.
    expected_rules = copy.deepcopy(DEFAULT_SECURITY_RULES)
    if ingress_tcp_ports:
        for tcp_port in ingress_tcp_ports:
            expected_rules[f"tcp{tcp_port}"] = {
                "protocol": "tcp",
                "port_range_min": tcp_port,
                "port_range_max": tcp_port,
                "direction": "ingress",
                "ethertype": "IPv4",
            }

    existing_rules = security_group.security_group_rules
    for expected_rule_name, expected_rule in expected_rules.items():
        expected_rule_found = False
        for existing_rule in existing_rules:
            if _rule_matches(existing_rule, expected_rule):
                expected_rule_found = True
                break
        if not expected_rule_found:
            missing_rules[expected_rule_name] = expected_rule
    return missing_rules


def _rule_matches(rule: SecurityGroupRule, expected_rule_dict: SecurityRuleDict) -> bool:
    """Check if an expected rule matches a security rule."""
    for condition_name, condition_value in expected_rule_dict.items():
        if rule[condition_name] != condition_value:
            return False
    return True
