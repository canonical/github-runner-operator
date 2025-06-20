# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class for accessing OpenStack API for managing servers."""
import copy
import logging
import multiprocessing
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence, cast

import jinja2
import openstack
import openstack.exceptions
from openstack.compute.v2.keypair import Keypair as OpenstackKeypair
from openstack.compute.v2.server import Server as OpenstackServer
from openstack.connection import Connection as OpenStackConnection
from openstack.network.v2.security_group import SecurityGroup as OpenstackSecurityGroup
from openstack.network.v2.security_group_rule import SecurityGroupRule

from github_runner_manager.configuration import SupportServiceConfig
from github_runner_manager.errors import OpenStackError
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient

logger = logging.getLogger(__name__)


_SecurityRuleDict = dict[str, Any]

_CREATE_SERVER_TIMEOUT = 5 * 60
_SECURITY_GROUP_NAME = "github-runner-v1"
_DEFAULT_SECURITY_RULES: dict[str, _SecurityRuleDict] = {
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

_RUNNER_LISTENER_PROCESS = "Runner.Listener"
_RUNNER_WORKER_PROCESS = "Runner.Worker"

_METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
_RUNNER_INSTALLED_TS_FILE_NAME = _METRICS_EXCHANGE_PATH / "runner-installed.timestamp"
_PRE_JOB_METRICS_FILE_NAME = _METRICS_EXCHANGE_PATH / "pre-job-metrics.json"
_POST_JOB_METRICS_FILE_NAME = _METRICS_EXCHANGE_PATH / "post-job-metrics.json"
_CREATE_SERVER_TIMEOUT = 5 * 60
_DELETE_SERVER_TIMEOUT = 5 * 60
_RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
_PRE_JOB_SCRIPT = _METRICS_EXCHANGE_PATH / "pre-job.sh"


@dataclass(frozen=True)
class VMConfig:
    """Configuration for a VM instance.

    Attributes:
        image: The image used to boot the VM.
        flavor: The flavor of the VM.
    """

    image: str
    flavor: str


class OpenStackServerStatus(str, Enum):
    """The OpenStack server status.

    Refer to the package: openstack.compute.v2.server.py:~L257, server.status
    field description.

    Attributes:
       ACTIVE: The server is active.
       BUILDING: The server is building.
       ERROR: The server is in error.
       SHUTOFF: The server is shut off.
       STOPPED: The server is stopped.
       UNKNOWN: The server status could not be verified.
    """

    ACTIVE = "ACTIVE"
    BUILDING = "BUILDING"
    ERROR = "ERROR"
    SHUTOFF = "SHUTOFF"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


class VMStatus(str, Enum):
    """Status of the VM.

    Attributes:
        ACTIVE: The VM is active and running.
        ERROR: The VM is in an error state.
        INITIALIZING: The VM is currently getting built.
        SHUTOFF: The VM is powered down.
    """

    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    INITIALIZING = "INITIALIZING"
    SHUTOFF = "SHUTOFF"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_openstack_server(cls, server: OpenstackServer):
        """Get the VM status from openstack server.

        Args:
            server: The OpenStack server instance.
        """
        try:
            status = OpenStackServerStatus(server.status)
        except ValueError as exc:
            return cls("UNKNOWN")

        match status:
            case OpenStackServerStatus.ACTIVE:
                return cls("ACTIVE")
            case OpenStackServerStatus


@dataclass(frozen=True)
class CloudVM:
    """The OpenStack VM instance.

    Attributes:
        instance_id: The ID of the VM instance.
        metadata: A key-value metadata attached to the VM instance, used to identify jobs running\
            on the VM.
        vm_config: The configuration used to create the VM.
    """

    instance_id: InstanceID
    metadata: dict[str, str]
    vm_config: VMConfig
    vm_status: VMStatus
    created_at: datetime

    @classmethod
    def from_openstack_server(cls, server: OpenstackServer, prefix: str):
        """Create an instance of OpenStackVM from an OpenstackServer instance.

        Args:
            server: The OpenStack server instance.
            prefix: The resource prefix (the unit name in the charm.)
        """
        return cls(
            instance_id=InstanceID.build_from_name(prefix=prefix, name=server.name),
            metadata=server.metadata,
            vm_config=VMConfig(image=server.image_id, flavor=server.flavor_id),
            vm_status=VMStatus.INITIALIZING,
            created_at=datetime.strptime(server.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            ),
        )


@dataclass(frozen=True)
class OpenStackConfig:
    """OpenStack configuration.

    Attributes:
        prefix: Prefix to use for the instances managed by this application.
        network: Network to use to spawn instances.
        key_dir: The path to store the SSH keys.
        system_user: The system user running the application to own any local resources.
    """

    prefix: str
    network: str
    key_dir: Path
    system_user: str
    ingress_tcp_ports: list[int] | None = None


class OpenStackCloud:
    """Interface for interacting with OpenStack resources."""

    def __init__(
        self,
        connection: OpenStackConnection,
        config: OpenStackConfig,
        service_config: SupportServiceConfig,
        repo_policy_compliance_service: RepoPolicyComplianceClient | None,
    ):
        """Initialize OpenStack service.

        Args:
            connection: The OpenStack connection.
            config: The OpenStack configuration for the application.
            service_config: The external service configuration values to setup the VM with.
            repo_policy_compliance_service: The Repo policy compliance service.
        """
        self._conn = connection
        self._config = config
        self._service_config = service_config
        self._repo_policy_service = repo_policy_compliance_service
        # 2025-06-20 This should be changed in reconciler for it to not require name_prefix.
        self.name_prefix = config.prefix

    def prepare_cloud(self) -> None:
        """Prepare cloud according to the configuration."""
        self._security_group = self._ensure_security_group(
            ingress_tcp_ports=self._config.ingress_tcp_ports
        )

    def list_vms(self) -> list[CloudVM]:
        """List all the VMs managed by the application."""
        servers = [
            server
            for server in cast(Iterable[OpenstackServer], self._conn.list_servers())
            if server.name.startswith(self._config.prefix)
        ]
        return [
            CloudVM.from_openstack_server(server=server, prefix=self._config.prefix)
            for server in servers
        ]

    def create_vm(
        self,
        *,
        instance_id: InstanceID,
        vm_config: VMConfig,
        metadata: dict[str, str],
        workload_start_script: str,
    ) -> CloudVM:
        """Create a virtual machine.

        Args:
            instance_id: Name of the unique instance id.
            vm_config: The configuration used to create the VM.
            metadata: Metadata to associate with the VM.
            workload_start_script: The script to start the workload. This script is different per \
                workload due to conditions like JIT tokens.
        """
        cloud_init = self._generate_cloud_init(workload_start_script=workload_start_script)

        # 2025-06-20 I'm not sure why we use prefix here given that instance_id already
        # encodes prefix into the name.
        metadata["prefix"] = self._config.prefix

        # create SSH key
        keypair: OpenstackKeypair = self._conn.create_keypair(name=str(instance_id))
        key_path = self._save_ssh_key(keypair=keypair, instance_id=instance_id)

        try:
            server = self._conn.create_server(
                name=instance_id,
                image=vm_config.image,
                key_name=keypair.name,
                flavor=vm_config.flavor,
                network=self._config.network,
                security_groups=[self._security_group],
                auto_ip=False,
                meta=metadata,
                userdata=cloud_init,
                timeout=_CREATE_SERVER_TIMEOUT,
                wait=True,
            )
        except openstack.exceptions.ResourceTimeout as err:
            self._conn.delete_server(name_or_id=instance_id)
            raise OpenStackError(f"Timeout creating openstack server {instance_id}") from err
        except openstack.exceptions.SDKException as err:
            self._conn.delete_keypair(name=keypair.name)
            key_path.unlink(missing_ok=True)
            raise OpenStackError(f"Failed to create openstack server {instance_id}") from err

        return CloudVM.from_openstack_server(server=server, prefix=self._config.prefix)

    def delete_vms(self, *, vms: Sequence[CloudVM]) -> list[CloudVM]:
        """Request VMs for deletion.

        Args:
            vms: The OpenStack vms to request deletion.

        Returns:
            The list if deleted VMs.
        """
        deleted_vms: list[CloudVM] = []
        delete_configs = [_DeleteVMConfig(vm=vm, conn=self._conn) for vm in vms]
        with multiprocessing.Pool(processes=min(len(delete_configs), 30)) as pool:
            jobs = pool.imap(func=_delete_multiprocess_wrapper, iterable=delete_configs)
            for delete_config in delete_configs:
                try:
                    deleted_vm = next(jobs)
                except openstack.exceptions.SDKException as exc:
                    logger.exception(
                        "Failed to delete VM %s, error: %s",
                        delete_config.vm.instance_id,
                        exc.message,
                    )
                    continue
                except StopIteration:
                    break
                if deleted_vm:
                    deleted_vms.append(deleted_vm)
        return deleted_vms

    def _generate_cloud_init(self, workload_start_script: str) -> str:
        """Generate cloud-init userdata.

        This is the script the openstack server runs on startup.

        Args:
            workload_start_script: The script used to start the workload.

        Returns:
            The cloud init userdata for openstack instance.
        """
        # We do not autoscape, the reason is that we are not generating html or xml
        jinja = jinja2.Environment(  # nosec
            loader=jinja2.PackageLoader("github_runner_manager", "templates")
        )

        service_config = self._service_config
        runner_http_proxy = (
            service_config.runner_proxy_config.proxy_address
            if service_config.runner_proxy_config
            else None
        )
        ssh_debug_info = (
            secrets.choice(service_config.ssh_debug_connections)
            if service_config.ssh_debug_connections
            else None
        )
        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(_PRE_JOB_SCRIPT),
            dockerhub_mirror=service_config.dockerhub_mirror or "",
            ssh_debug_info=ssh_debug_info,
            tmate_server_proxy=runner_http_proxy,
        )
        pre_job_contents_dict = {
            "issue_metrics": True,
            "metrics_exchange_path": str(_METRICS_EXCHANGE_PATH),
            "do_repo_policy_check": False,
            "custom_pre_job_script": service_config.custom_pre_job_script,
        }
        if self._repo_policy_service is not None:
            pre_job_contents_dict.update(
                {
                    "repo_policy_base_url": self._repo_policy_service.base_url,
                    "repo_policy_one_time_token": self._repo_policy_service.get_one_time_token(),
                    "do_repo_policy_check": True,
                }
            )

        pre_job_contents = jinja.get_template("pre-job.j2").render(pre_job_contents_dict)

        aproxy_address = (
            service_config.runner_proxy_config.proxy_address
            if service_config.use_aproxy and service_config.runner_proxy_config
            else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            run_script=workload_start_script,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(_METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=service_config.dockerhub_mirror,
            ssh_debug_info=ssh_debug_info,
            runner_proxy_config=service_config.runner_proxy_config,
        )

    def _save_ssh_key(self, keypair: OpenstackKeypair, instance_id: InstanceID) -> Path:
        """Save OpenStack SSH key in SSH dir.

        Args:
            keypair: The OpenStack keypair to save.
            instance_id: The owner instnace of the key.
        """
        key_path = self._config.key_dir / f"{instance_id}.key"
        if key_path.exists():
            logger.warning("Existing private key file for %s found, removing it.", instance_id)
            key_path.unlink(missing_ok=True)
        key_path.write_text(keypair.private_key)
        # the charm executes this as root, so we need to change the ownership of the key file
        shutil.chown(key_path, user=self._config.system_user)
        key_path.chmod(0o400)
        return key_path

    def _ensure_security_group(
        self, ingress_tcp_ports: list[int] | None
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
        security_group_list = self._conn.list_security_groups(
            filters={"name": _SECURITY_GROUP_NAME}
        )
        # Pick the first security_group returned.
        security_group: OpenstackSecurityGroup | None = next(iter(security_group_list), None)
        if security_group is None:
            security_group = cast(
                OpenstackSecurityGroup,
                self._conn.create_security_group(
                    name=_SECURITY_GROUP_NAME,
                    description="For servers managed by the github-runner charm.",
                ),
            )

        # Check if there are any missing rules and create them if so.
        missing_rules = _get_missing_security_rules(
            security_group=security_group, ingress_tcp_ports=ingress_tcp_ports
        )
        for missing_rule_name, missing_rule in missing_rules.items():
            self._conn.create_security_group_rule(
                secgroup_name_or_id=security_group.id, **missing_rule
            )

        return security_group


def _get_missing_security_rules(
    security_group: OpenstackSecurityGroup, ingress_tcp_ports: list[int] | None
) -> dict[str, _SecurityRuleDict]:
    """Get security rules to add to the security group.

    Args:
        security_group: The security group where rules will be added.
        ingress_tcp_ports: Ports to create an ingress rule for.

    Returns:
        A dictionary with the rules that should be added to the security group.
    """
    missing_rules: dict[str, _SecurityRuleDict] = {}

    # We do not want to mess with the default security rules, so the deepcopy.
    expected_rules = copy.deepcopy(_DEFAULT_SECURITY_RULES)
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


def _rule_matches(rule: SecurityGroupRule, expected_rule_dict: _SecurityRuleDict) -> bool:
    """Check if an expected rule matches a security rule."""
    for condition_name, condition_value in expected_rule_dict.items():
        if rule[condition_name] != condition_value:
            return False
    return True


@dataclass(frozen=True)
class _DeleteVMConfig:
    """Delete VM configuration wrapper for multiprocessed delete operation.

    Attributes:
        vm: The VM to delete.
        conn: The OpenStack connection.
    """

    vm: CloudVM
    conn: OpenStackConnection


def _delete_multiprocess_wrapper(config: _DeleteVMConfig) -> CloudVM | None:
    """Batch delete OpenStack VMs using multiprocessing.

    Args:
        vm: The VM to request deletion.

    Returns:
        OpenStack VM if it was deleted. None if it does not exist.
    """
    return (
        config.vm
        if config.conn.delete_server(
            name_or_id=config.vm.instance_id, wait=True, timeout=_DELETE_SERVER_TIMEOUT
        )
        else None
    )
