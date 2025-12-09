#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
from asyncio import sleep
from typing import TypedDict

import openstack.connection
from github_runner_manager import constants
from juju.application import Application
from juju.unit import Unit
from openstack.compute.v2.server import Server

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import run_in_unit, wait_for_runner_ready

logger = logging.getLogger(__name__)


class OpenStackInstanceHelper:
    """Helper class to interact with OpenStack instances."""

    def __init__(self, openstack_connection: openstack.connection.Connection):
        """Initialize OpenStackInstanceHelper.

        Args:
            openstack_connection: OpenStack connection object.
        """
        self.openstack_connection = openstack_connection

    async def expose_to_instance(
        self,
        unit: Unit,
        port: int,
        host: str = "localhost",
    ) -> None:
        """Expose a port on the juju machine to the OpenStack instance.

        Uses SSH remote port forwarding from the juju machine to the OpenStack instance containing
        the runner.

        Args:
            unit: The juju unit of the github-runner charm.
            port: The port on the juju machine to expose to the runner.
            host: Host for the reverse tunnel.
        """
        runner = self.get_single_runner(unit=unit)
        assert runner, f"Runner not found for unit {unit.name}"
        logger.info("[TEST SETUP] Exposing port %s on %s", port, runner.name)
        network_address_list = runner.addresses.values()
        logger.warning(network_address_list)
        assert (
            network_address_list
        ), f"No addresses to connect to for OpenStack server {runner.name}"

        ip = None
        for network_addresses in network_address_list:
            for address in network_addresses:
                ip = address["addr"]
                break
        assert ip, f"Failed to get IP address for OpenStack server {runner.name}"

        key_path = f"/home/{constants.RUNNER_MANAGER_USER}/.ssh/{runner.name}.key"
        exit_code, _, _ = await run_in_unit(unit, f"ls {key_path}")
        assert exit_code == 0, f"Unable to find key file {key_path}"
        ssh_cmd = f'ssh -fNT -R {port}:{host}:{port} -i {key_path} -o "StrictHostKeyChecking no" -o "ControlPersist yes" ubuntu@{ip} &'
        logger.info("ssh tunnel command %s", ssh_cmd)
        exit_code, stdout, stderr = await run_in_unit(unit, ssh_cmd)
        logger.info("ssh tunnel result %s %s %s", exit_code, stdout, stderr)
        assert (
            exit_code == 0
        ), f"Error in starting background process of SSH remote forwarding of port {port}: {stderr}"

        await sleep(1)
        for _ in range(10):
            exit_code, _, _ = await self.run_in_instance(
                unit=unit, command=f"nc -z localhost {port}"
            )
            if exit_code == 0:
                return
            await sleep(10)
        assert False, f"Exposing the port {port} failed"

    async def run_in_instance(
        self,
        unit: Unit,
        command: str,
        timeout: int | None = None,
        assert_on_failure: bool = False,
        assert_msg: str | None = None,
    ) -> tuple[int, str | None, str | None]:
        """Run command in OpenStack instance.

        Args:
            unit: Juju unit to execute the command in.
            command: Command to execute.
            timeout: Amount of time to wait for the execution.
            assert_on_failure: Perform assertion on non-zero exit code.
            assert_msg: Message for the failure assertion.

        Returns:
            Tuple of return code, stdout and stderr.
        """
        runner = self.get_single_runner(unit=unit)
        assert runner, f"Runner not found for unit {unit.name}"
        logger.info("[TEST SETUP] Run command %s on %s", command, runner.name)
        network_address_list = runner.addresses.values()
        logger.warning(network_address_list)
        assert (
            network_address_list
        ), f"No addresses to connect to for OpenStack server {runner.name}"

        ip = None
        for network_addresses in network_address_list:
            for address in network_addresses:
                ip = address["addr"]
                break
        assert ip, f"Failed to get IP address for OpenStack server {runner.name}"

        key_path = f"/home/{constants.RUNNER_MANAGER_USER}/.ssh/{runner.name}.key"
        exit_code, _, _ = await run_in_unit(unit, f"ls {key_path}")
        assert exit_code == 0, f"Unable to find key file {key_path}"
        ssh_cmd = f'ssh -i {key_path} -o "StrictHostKeyChecking no" ubuntu@{ip} {command}'
        ssh_cmd_as_ubuntu_user = f"su - ubuntu -c '{ssh_cmd}'"
        logging.warning("ssh_cmd: %s", ssh_cmd_as_ubuntu_user)
        exit_code, stdout, stderr = await run_in_unit(unit, ssh_cmd, timeout)
        logger.info(
            "Run command '%s' in runner with result %s: '%s' '%s'",
            command,
            exit_code,
            stdout,
            stderr,
        )
        if assert_on_failure:
            assert exit_code == 0, assert_msg
        return exit_code, stdout, stderr

    async def ensure_charm_has_runner(self, app: Application) -> None:
        """Reconcile the charm to contain one runner.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
        """
        await OpenStackInstanceHelper.set_app_runner_amount(app, 1)

    @staticmethod
    async def set_app_runner_amount(app: Application, num_runners: int) -> None:
        """Reconcile the application to a runner amount.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
            num_runners: The number of runners.
        """
        await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: f"{num_runners}"})
        await wait_for_runner_ready(app=app)

    async def get_runner_names(self, unit: Unit) -> list[str]:
        """Get the name of all the runners in the unit.

        Args:
            unit: The GitHub Runner Charm unit to get the runner names for.

        Returns:
            List of names for the runners.
        """
        runners = self._get_runners(unit)
        return [runner.name for runner in runners]

    async def get_runner_name(self, unit: Unit) -> str:
        """Get the name of the runner.

        Expects only one runner to be present.

        Args:
            unit: The GitHub Runner Charm unit to get the runner name for.

        Returns:
            The Github runner name deployed in the given unit.
        """
        runners = self._get_runners(unit)
        assert len(runners) == 1
        return runners[0].name

    async def delete_single_runner(self, unit: Unit) -> None:
        """Delete the only runner.

        Args:
            unit: The GitHub Runner Charm unit to delete the runner name for.
        """
        runner = self.get_single_runner(unit)
        self.openstack_connection.delete_server(name_or_id=runner.id)

    def _get_runners(self, unit: Unit) -> list[Server]:
        """Get all runners for the unit."""
        servers: list[Server] = self.openstack_connection.list_servers()
        unit_name_without_slash = unit.name.replace("/", "-")
        runners = [server for server in servers if server.name.startswith(unit_name_without_slash)]
        return runners

    def get_single_runner(self, unit: Unit) -> Server:
        """Get the only runner for the unit.

        This method asserts for exactly one runner for the unit.

        Args:
            unit: The unit to get the runner for.

        Returns:
            The runner server.
        """
        runners = self._get_runners(unit)
        assert (
            len(runners) == 1
        ), f"In {unit.name} found more than one runners or no runners: {runners}"
        return runners[0]


class PrivateEndpointConfigs(TypedDict):
    """The Private endpoint configuration values.

    Attributes:
        auth_url: OpenStack uthentication URL (Keystone).
        password: OpenStack password.
        project_domain_name: OpenStack project domain to use.
        project_name: OpenStack project to use within the domain.
        user_domain_name: OpenStack user domain to use.
        username: OpenStack user to use within the domain.
        region_name: OpenStack deployment region.
    """

    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str
    region_name: str
