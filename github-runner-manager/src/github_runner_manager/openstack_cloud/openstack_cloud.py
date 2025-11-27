# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for accessing OpenStack API for managing servers."""
import concurrent.futures
import contextlib
import copy
import functools
import logging
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, ParamSpec, Sequence, TypeVar, cast

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
from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.openstack_cloud.configuration import OpenStackCredentials
from github_runner_manager.openstack_cloud.constants import (
    CREATE_SERVER_TIMEOUT,
    OPENSTACK_API_TIMEOUT,
)
from github_runner_manager.openstack_cloud.models import OpenStackServerConfig

logger = logging.getLogger(__name__)

# Update the version when the security group rules are not backward compatible.
_SECURITY_GROUP_NAME = "github-runner-v1"

_SSH_TIMEOUT = 30
_TEST_STRING = "test_string"
# Max nova compute we support is 2.91, because
# - 2.96 has a bug with server list  https://bugs.launchpad.net/nova/+bug/2095364
# - 2.92 requires public key to be set in the keypair, which is not supported by the app
#        https://docs.openstack.org/api-ref/compute/#import-or-create-keypair
_MAX_NOVA_COMPUTE_API_VERSION = "2.91"

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


class DeleteVMError(openstack.exceptions.SDKException):
    """Represents an error while deleting a VM instance.

    Attributes:
        instance_id: The instance ID that was failed to delete.
    """

    instance_id: InstanceID

    def __init__(
        self, instance_id: InstanceID, message: str | None = None, extra_data: Any = None
    ):
        """Initialize the OpenstackVMDeleteError.

        Args:
            instance_id: The instance ID of the failed delete VM.
            message: The delete error message for parent SDKException.
            extra_data: Extra data for parent SDKException if any.
        """
        self.instance_id = instance_id
        super().__init__(message, extra_data)


@dataclass(frozen=True)
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

    @classmethod
    def from_openstack_server(cls, server: OpenstackServer, prefix: str) -> "OpenstackInstance":
        """Construct the object.

        Args:
            server: The OpenStack server.
            prefix: The name prefix for the servers.

        Returns:
            The OpenstackInstance.
        """
        return cls(
            addresses=[
                address["addr"]
                for network_addresses in server.addresses.values()
                for address in network_addresses
            ],
            created_at=datetime.strptime(server.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            ),
            instance_id=InstanceID.build_from_name(prefix, server.name),
            server_id=server.id,
            status=server.status,
            # To be backwards compatible, we need a default RunnerMetadata.
            metadata=RunnerMetadata(**server.metadata) if server.metadata else RunnerMetadata(),
        )


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


@dataclass
class _DeleteVMConfig:
    """Configurations for deleting a VM.

    Attributes:
        instance_id: The ID of the VM to request deletion.
        credentials: The OpenStack connection credentials.
        max_api_version: The OpenStack maximum compute API version.
        keys_dir: The path to the directory in which the SSH key files are stored.
        wait: Whether to wait for the VM delete to complete.
        timeout: Timeout in seconds for VM deletion to complete.
    """

    instance_id: InstanceID
    credentials: OpenStackCredentials
    max_api_version: str
    keys_dir: Path
    wait: bool = False
    timeout: int = 10 * 60


@dataclass
class _DeleteKeypairConfig:
    """Configurations for deleting an OpenStack keypair.

    Attributes:
        keys_dir: The path to the directory in which the SSH key files are stored.
        instance_id: The instance ID of the key owner.
        conn: The OpenStack connection instance.
    """

    keys_dir: Path
    instance_id: InstanceID
    conn: OpenstackConnection


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
    def launch_instance(
        self,
        *,
        runner_identity: RunnerIdentity,
        server_config: OpenStackServerConfig,
        cloud_init: str,
        ingress_tcp_ports: list[int] | None = None,
    ) -> OpenstackInstance:
        """Create an OpenStack instance.

        Args:
            runner_identity: Identity of the runner.
            server_config: Configuration for the instance to create.
            cloud_init: The cloud init userdata to startup the instance.
            ingress_tcp_ports: Ports to be allowed to connect to the new instance.

        Raises:
            OpenStackError: Unable to create OpenStack server.

        Returns:
            The OpenStack instance created.
        """
        logger.info("Creating openstack server with %s", runner_identity)
        instance_id = runner_identity.instance_id
        metadata = runner_identity.metadata

        with self._get_openstack_connection() as conn:
            security_group = OpenstackCloud._ensure_security_group(conn, ingress_tcp_ports)
            keypair = self._setup_keypair(conn, runner_identity.instance_id)
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
                    wait=False,
                    meta=meta,
                    # 2025/07/24 - This option is set to mitigate CVE-2024-6174
                    config_drive=True,
                )
            except openstack.exceptions.ResourceTimeout as err:
                logger.exception("Timeout creating openstack server %s", instance_id)
                logger.info(
                    "Attempting clean up of openstack server %s that timeout during creation",
                    instance_id,
                )
                OpenstackCloud._delete_instance(
                    _DeleteVMConfig(
                        instance_id=instance_id,
                        credentials=self._credentials,
                        max_api_version=self._max_compute_api_version,
                        keys_dir=self._ssh_key_dir,
                    )
                )
                raise OpenStackError(f"Timeout creating openstack server {instance_id}") from err
            except openstack.exceptions.SDKException as err:
                logger.exception("Failed to create openstack server %s", instance_id)
                OpenstackCloud._delete_keypair(
                    _DeleteKeypairConfig(
                        keys_dir=self._ssh_key_dir, instance_id=instance_id, conn=conn
                    )
                )
                raise OpenStackError(f"Failed to create openstack server {instance_id}") from err

            return OpenstackInstance.from_openstack_server(server, self.prefix)

    @_catch_openstack_errors
    def get_instance(self, instance_id: InstanceID) -> OpenstackInstance | None:
        """Get OpenStack instance by instance ID.

        Args:
            instance_id: The instance ID.

        Returns:
            The OpenStack instance if found.
        """
        logger.info("Getting openstack server with %s", instance_id)

        with self._get_openstack_connection() as conn:
            server: OpenstackServer = conn.get_server(name_or_id=instance_id.name)
            if server is not None:
                return OpenstackInstance.from_openstack_server(server, self.prefix)
        return None

    @staticmethod
    def _delete_instance(delete_config: _DeleteVMConfig) -> bool:
        """Delete a openstack instance.

        Args:
            delete_config: The configuration used to delete a cloud VM instance.

        Raises:
            DeleteVMError: If there was an error deleting the VM instance.
        """
        with openstack.connect(
            auth_url=delete_config.credentials.auth_url,
            project_name=delete_config.credentials.project_name,
            username=delete_config.credentials.username,
            password=delete_config.credentials.password,
            region_name=delete_config.credentials.region_name,
            user_domain_name=delete_config.credentials.user_domain_name,
            project_domain_name=delete_config.credentials.project_domain_name,
            compute_api_version=delete_config.max_api_version,
        ) as conn:
            try:
                logger.info("Deleting server %s", delete_config.instance_id.name)
                deleted = conn.delete_server(
                    name_or_id=delete_config.instance_id.name,
                    wait=delete_config.wait,
                    timeout=delete_config.timeout,
                )
                logger.info(
                    "Deleted server %s (true delete: %s)", delete_config.instance_id.name, deleted
                )
            except (
                openstack.exceptions.SDKException,
                openstack.exceptions.ResourceTimeout,
            ) as exc:
                raise DeleteVMError(
                    instance_id=delete_config.instance_id,
                    message=f"Failed to delete server {delete_config.instance_id.name}",
                ) from exc

            OpenstackCloud._delete_keypair(
                _DeleteKeypairConfig(
                    keys_dir=delete_config.keys_dir,
                    instance_id=delete_config.instance_id,
                    conn=conn,
                )
            )

        return deleted

    def delete_instances(
        self, instance_ids: Sequence[InstanceID], wait: bool = False, timeout: int = 60 * 10
    ) -> list[InstanceID]:
        """Delete Openstack VM instances.

        Args:
            instance_ids: The VM instance IDs to requeest deletion.
            wait: Whether to wait for VM deletion to complete.
            timeout: Timeout in seconds to wait for VM deletion to complete.

        Returns:
            The deleted VM instance IDs if wait is True, deleted requested VM instance IDs
            otherwise.
        """
        deleted_instance_ids: list[InstanceID] = []

        # Guard no instance IDs since multiprocessing Pool may raise an exception.
        if not instance_ids:
            return deleted_instance_ids

        delete_configs = [
            _DeleteVMConfig(
                instance_id=instance_id,
                credentials=self._credentials,
                max_api_version=self._max_compute_api_version,
                keys_dir=self._ssh_key_dir,
                wait=wait,
                timeout=timeout,
            )
            for instance_id in instance_ids
        ]
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(instance_ids), 30)
        ) as executor:
            future_to_delete_instance_config = {
                executor.submit(OpenstackCloud._delete_instance, config): config
                for config in delete_configs
            }
            for future in concurrent.futures.as_completed(future_to_delete_instance_config):
                delete_config = future_to_delete_instance_config[future]
                try:
                    if not future.result():
                        continue
                    deleted_instance_ids.append(delete_config.instance_id)
                except DeleteVMError as exc:
                    logger.error("Failed to delete OpenStack VM instance: %s", exc.instance_id)

        return deleted_instance_ids

    @_catch_openstack_errors
    @contextlib.contextmanager
    def get_ssh_connection(self, instance: OpenstackInstance) -> Iterator[SSHConnection]:
        """Get SSH connection to an OpenStack instance.

        Args:
            instance: The OpenStack instance to connect to.

        Raises:
            SSHError: Unable to get a working SSH connection to the instance.
            KeyfileError: Unable to find the keyfile to connect to the instance.

        Yields:
            SSH connection object.
        """
        key_path = self._get_key_path(instance.instance_id)

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
                    yield connection
                    break
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
            finally:
                connection.close()
        else:
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

        with self._get_openstack_connection() as conn:
            instance_list = list(self._get_openstack_instances(conn))
            server_names = set(server.name for server in instance_list)

            server_list = [
                OpenstackCloud._get_and_ensure_unique_server(conn, name, instance_list)
                for name in server_names
            ]
            return tuple(
                OpenstackInstance.from_openstack_server(server, self.prefix)
                for server in server_list
                if server is not None
            )

    @_catch_openstack_errors
    def delete_expired_keys(self) -> None:
        """Cleanup unused key files and openstack keypairs."""
        with self._get_openstack_connection() as conn:
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
                    OpenstackCloud._delete_keypair(
                        _DeleteKeypairConfig(
                            keys_dir=self._ssh_key_dir,
                            instance_id=InstanceID.build_from_name(self.prefix, key.name),
                            conn=conn,
                        )
                    )
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

    @staticmethod
    def _delete_keypair(delete_keypair_config: _DeleteKeypairConfig) -> None:
        """Delete OpenStack keypair.

        Args:
            delete_keypair_config: Configurations for deleting the KeyPair.
        """
        logger.info("Deleting key: %s", delete_keypair_config.instance_id)
        try:
            # Keypair have unique names, access by ID is not needed.
            if not delete_keypair_config.conn.delete_keypair(
                delete_keypair_config.instance_id.name
            ):
                logger.warning("Failed to delete key: %s", delete_keypair_config.instance_id.name)
                return
        except (openstack.exceptions.SDKException, openstack.exceptions.ResourceTimeout):
            logger.warning(
                "Error attempting to delete key: %s",
                delete_keypair_config.instance_id.name,
                stack_info=True,
            )
            return

        key_path = delete_keypair_config.keys_dir / f"{delete_keypair_config.instance_id}.key"
        key_path.unlink(missing_ok=True)
        logger.info("Deleted key: %s", delete_keypair_config.instance_id)

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

    @contextmanager
    def _get_openstack_connection(self) -> Iterator[OpenstackConnection]:
        """Create a connection context managed object, to be used within with statements.

        Using the context manager ensures that the connection is properly closed after use.

        Yields:
            An openstack.connection.Connection object.
        """
        # api documents that keystoneauth1.exceptions.MissingRequiredOptions can be raised but
        # I could not reproduce it. Therefore, no catch here for such exception.

        with openstack.connect(
            auth_url=self._credentials.auth_url,
            project_name=self._credentials.project_name,
            username=self._credentials.username,
            password=self._credentials.password,
            region_name=self._credentials.region_name,
            user_domain_name=self._credentials.user_domain_name,
            project_domain_name=self._credentials.project_domain_name,
            compute_api_version=self._max_compute_api_version,
        ) as conn:
            conn.authorize()
            yield conn

    @functools.cached_property
    def _max_compute_api_version(self) -> str:
        """Determine the maximum compute API version supported by the client.

        The sdk does not support versions greater than 2.95, so we need to ensure that the
        maximum version returned by the OpenStack cloud is not greater than that.
        https://bugs.launchpad.net/nova/+bug/2095364

        Returns:
            The maximum compute API version to use for the client.
        """
        max_version = self._determine_max_compute_api_version_by_cloud()
        if self._version_greater_than(max_version, _MAX_NOVA_COMPUTE_API_VERSION):
            logger.warning(
                "The maximum compute API version %s is greater than the supported version %s. "
                "Using the maximum supported version.",
                max_version,
                _MAX_NOVA_COMPUTE_API_VERSION,
            )
            return _MAX_NOVA_COMPUTE_API_VERSION
        return max_version

    def _determine_max_compute_api_version_by_cloud(self) -> str:
        """Determine the maximum compute API version supported by the OpenStack cloud.

        Returns:
            The maximum compute API version as a string.
        """
        with openstack.connect(
            auth_url=self._credentials.auth_url,
            project_name=self._credentials.project_name,
            username=self._credentials.username,
            password=self._credentials.password,
            region_name=self._credentials.region_name,
            user_domain_name=self._credentials.user_domain_name,
            project_domain_name=self._credentials.project_domain_name,
        ) as conn:
            version_endpoint = conn.compute.get_endpoint()
            resp = conn.session.get(version_endpoint, timeout=OPENSTACK_API_TIMEOUT)
            return resp.json()["version"]["version"]

    def _version_greater_than(self, version1: str, version2: str) -> bool:
        """Compare two OpenStack API versions.

        Args:
            version1: The first version to compare.
            version2: The second version to compare.

        Returns:
            True if version1 is greater than version2, False otherwise.
        """
        return tuple(int(x) for x in version1.split(".")) > tuple(
            int(x) for x in version2.split(".")
        )


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
