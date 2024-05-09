#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
from typing import cast

import openstack.connection
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.compute.v2.server import Server

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import InstanceHelper, reconcile, run_in_unit

logger = logging.getLogger(__name__)


class OpenStackInstanceHelper(InstanceHelper):
    """Helper class to interact with OpenStack instances."""

    def __init__(self, openstack_connection: openstack.connection.Connection):
        """Initialize OpenStackInstanceHelper.

        Args:
            openstack_connection: OpenStack connection object.
        """
        self.openstack_connection = openstack_connection

    async def run_in_instance(
        self,
        unit: Unit,
        command: str,
        timeout: int | None = None,
    ) -> tuple[int, str | None, str | None]:
        """Run command in OpenStack instance.

        Args:
            unit: Juju unit to execute the command in.
            command: Command to execute.
            timeout: Amount of time to wait for the execution.

        Returns:
            Tuple of return code, stdout and stderr.
        """
        runner = self._get_runner(unit=unit)
        assert runner, f"Runner not found for unit {unit.name}"
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

        ssh_cmd = f'ssh -i /home/ubuntu/.ssh/runner-{runner.name}.key -o "StrictHostKeyChecking no" ubuntu@{ip} {command}'
        ssh_cmd_as_ubuntu_user = f"su - ubuntu -c '{ssh_cmd}'"
        logging.warning("ssh_cmd: %s", ssh_cmd_as_ubuntu_user)
        return await run_in_unit(unit, ssh_cmd, timeout)

    async def ensure_charm_has_runner(self, app: Application, model: Model) -> None:
        """Reconcile the charm to contain one runner.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
            model: The machine charm model.
        """
        await OpenStackInstanceHelper._set_app_runner_amount(app, model, 1)

    @staticmethod
    async def _set_app_runner_amount(app: Application, model: Model, num_runners: int) -> None:
        """Reconcile the application to a runner amount.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
            model: The machine charm model.
            num_runners: The number of runners.
        """
        await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: f"{num_runners}"})
        await reconcile(app=app, model=model)

    async def get_runner_name(self, unit: Unit) -> str:
        """Get the name of the runner.

        Expects only one runner to be present.

        Args:
            unit: The GitHub Runner Charm unit to get the runner name for.

        Returns:
            The Github runner name deployed in the given unit.
        """
        runners = await self._get_runner_names(unit)
        assert len(runners) == 1
        return runners[0]

    async def _get_runner_names(self, unit: Unit) -> tuple[str, ...]:
        """Get names of the runners in LXD.

        Args:
            unit: Unit instance to check for the LXD profile.

        Returns:
            Tuple of runner names.
        """
        runner = self._get_runner(unit)
        assert runner, "Failed to find runner server"
        return (cast(str, runner.name),)

    def _get_runner(self, unit: Unit) -> Server | None:
        """Get the runner server.

        Args:
            unit: The unit to get the runner for.

        Returns:
            The runner server.
        """
        servers: list[Server] = self.openstack_connection.list_servers()
        runner = None
        unit_name_without_slash = unit.name.replace("/", "-")
        for server in servers:
            if server.name.startswith(unit_name_without_slash):
                runner = server
                break

        return runner
