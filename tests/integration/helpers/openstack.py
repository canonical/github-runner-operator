#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import asyncio
import logging
import secrets
from typing import Optional, cast

import openstack.connection
from juju.application import Application
from juju.unit import Unit
from openstack.compute.v2.server import Server

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import InstanceHelper, reconcile, run_in_unit, wait_for

logger = logging.getLogger(__name__)


class OpenStackInstanceHelper(InstanceHelper):
    """Helper class to interact with OpenStack instances."""

    def __init__(self, openstack_connection: openstack.connection.Connection):
        """Initialize OpenStackInstanceHelper.

        Args:
            openstack_connection: OpenStack connection object.
        """
        self.openstack_connection = openstack_connection

    async def install_repo_policy_in_instance(
        self,
        unit: Unit,
        github_token: str,
        charm_token: str,
        https_proxy: str,
        timeout: int | None = None,
    ) -> None:
        await self.run_in_instance(
            unit,
            "sudo apt install -y python3-pip",
            assert_on_failure=True,
            assert_msg="Failed to install python3-pip",
        )
        await self.run_in_instance(
            unit,
            "sudo rm -rf /home/ubuntu/repo_policy_compliance",
            assert_on_failure=True,
            assert_msg="Failed to remove repo-policy-compliance",
        )
        await self.run_in_instance(
            unit,
            f'sudo -u ubuntu HTTPS_PROXY={https_proxy if https_proxy else ""} git clone https://github.com/canonical/repo-policy-compliance.git /home/ubuntu/repo_policy_compliance',
            assert_on_failure=True,
            assert_msg="Failed to clone repo-policy-compliance",
        )
        await self.run_in_instance(
            unit,
            f'sudo -u ubuntu HTTPS_PROXY={https_proxy if https_proxy else ""} pip install --proxy http://squid.internal:3128 -r /home/ubuntu/repo_policy_compliance/requirements.txt',
            assert_on_failure=True,
            assert_msg="Failed to install repo-policy-compliance requirements",
        )
        await self.run_in_instance(
            unit=unit,
            command=f"HTTPS_PROXY={https_proxy if https_proxy else ''} sudo python3 -m pip install gunicorn",
            assert_on_failure=True,
            assert_msg="Failed to install gunicorn",
        )
        await self.run_in_instance(
            unit,
            f"""sudo tee -a /etc/systemd/system/repo-policy-compliance.service > /dev/null << EOT
[Unit]
Description=Simple HTTP server for testing
After=network.target

[Service]
User=ubuntu
Group=www-data
Environment="GITHUB_TOKEN={github_token}"
Environment="CHARM_TOKEN={charm_token}"
Environment="HTTPS_PROXY={https_proxy if https_proxy else ""}"
Environment="https_proxy={https_proxy if https_proxy else ""}"
WorkingDirectory=/home/ubuntu/repo_policy_compliance
ExecStart=/usr/local/bin/gunicorn --bind 0.0.0.0:8080 --timeout 60 app:app
EOT""",
            assert_on_failure=True,
            assert_msg="Failed to create service file",
        )
        await self.run_in_instance(
            unit,
            "sudo /usr/bin/systemctl daemon-reload",
            assert_on_failure=True,
            assert_msg="Failed to reload systemd",
        )
        await self.run_in_instance(
            unit,
            "sudo /usr/bin/systemctl restart repo-policy-compliance",
            assert_on_failure=True,
            assert_msg="Failed to restart service",
        )

    async def expose_to_instance(
        self,
        unit: Unit,
        port: int,
    ) -> None:
        """
        TODO
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

        ssh_cmd = f'ssh -fNT -R {port}:localhost:{port} -i /home/ubuntu/.ssh/runner-{runner.name}.key -o "StrictHostKeyChecking no" -o "ControlPersist yes" ubuntu@{ip} &'
        exit_code, stdout, stderr = await run_in_unit(unit, ssh_cmd)
        logger.debug(
            "Expose juju unit port to runner with result %s: '%s' '%s'",
            exit_code,
            stdout,
            stderr,
        )

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
        exit_code, stdout, stderr = await run_in_unit(unit, ssh_cmd, timeout)
        logger.debug(
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
        await OpenStackInstanceHelper._set_app_runner_amount(app, 1)

    @staticmethod
    async def _set_app_runner_amount(app: Application, num_runners: int) -> None:
        """Reconcile the application to a runner amount.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
            num_runners: The number of runners.
        """
        await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: f"{num_runners}"})
        await reconcile(app=app, model=app.model)

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


async def setup_repo_policy(
    app: Application,
    openstack_connection: openstack.connection.Connection,
    token: str,
    https_proxy: Optional[str],
) -> None:
    """Setup the repo policy compliance service for one runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        openstack_connection: OpenStack connection object.
        token: GitHub token.
        https_proxy: HTTPS proxy url to use.
    """
    unit = app.units[0]
    charm_token = secrets.token_hex(16)
    await _install_repo_policy(
        unit=unit, github_token=token, charm_token=charm_token, https_proxy=https_proxy
    )
    instance_helper = OpenStackInstanceHelper(openstack_connection)

    unit_address = await unit.get_public_address()
    await app.expose()
    unit_name_without_slash = unit.name.replace("/", "-")
    await run_in_unit(
        unit=unit,
        command=f"/var/lib/juju/tools/unit-{unit_name_without_slash}/open-port 8080",
        assert_on_failure=True,
        assert_msg="Failed to open port 8080",
    )
    await app.set_config(
        {
            "repo-policy-compliance-token": charm_token,
            "repo-policy-compliance-url": f"http://{unit_address}:8080",
        }
    )

    await instance_helper.ensure_charm_has_runner(app=app)
    await instance_helper.expose_to_instance(unit, 8080)

async def _install_repo_policy(
    unit: Unit, github_token: str, charm_token: str, https_proxy: Optional[str]
):
    """Start the repo policy compliance service.

    Args:
        unit: Unit instance to check for the LXD profile.
        github_token: GitHub token to use in the repo-policy service.
        charm_token: Charm token to use in the repo-policy service.
        https_proxy: HTTPS proxy url to use.
    """
    await run_in_unit(
        unit,
        "apt install -y python3-pip",
        assert_on_failure=True,
        assert_msg="Failed to install python3-pip",
    )
    await run_in_unit(
        unit,
        "rm -rf /home/ubuntu/repo_policy_compliance",
        assert_on_failure=True,
        assert_msg="Failed to remove repo-policy-compliance",
    )
    await run_in_unit(
        unit,
        f'sudo -u ubuntu HTTPS_PROXY={https_proxy if https_proxy else ""} git clone https://github.com/canonical/repo-policy-compliance.git /home/ubuntu/repo_policy_compliance',
        assert_on_failure=True,
        assert_msg="Failed to clone repo-policy-compliance",
    )
    await run_in_unit(
        unit,
        f'sudo -u ubuntu HTTPS_PROXY={https_proxy if https_proxy else ""} pip install --proxy http://squid.internal:3128 -r /home/ubuntu/repo_policy_compliance/requirements.txt',
        assert_on_failure=True,
        assert_msg="Failed to install repo-policy-compliance requirements",
    )
    await run_in_unit(
        unit=unit,
        command=f"HTTPS_PROXY={https_proxy if https_proxy else ''} python3 -m pip install gunicorn",
        assert_on_failure=True,
        assert_msg="Failed to install gunicorn",
    )
    await run_in_unit(
        unit,
        f"""cat <<EOT > /etc/systemd/system/repo-policy-compliance.service
[Unit]
Description=Simple HTTP server for testing
After=network.target

[Service]
User=ubuntu
Group=www-data
Environment="GITHUB_TOKEN={github_token}"
Environment="CHARM_TOKEN={charm_token}"
Environment="HTTPS_PROXY={https_proxy if https_proxy else ""}"
Environment="https_proxy={https_proxy if https_proxy else ""}"
WorkingDirectory=/home/ubuntu/repo_policy_compliance
ExecStart=/usr/local/bin/gunicorn --bind 0.0.0.0:8080 --timeout 60 app:app
EOT""",
        assert_on_failure=True,
        assert_msg="Failed to create service file",
    )
    await run_in_unit(
        unit,
        "/usr/bin/systemctl daemon-reload",
        assert_on_failure=True,
        assert_msg="Failed to reload systemd",
    )
    await run_in_unit(
        unit,
        "/usr/bin/systemctl restart repo-policy-compliance",
        assert_on_failure=True,
        assert_msg="Failed to restart service",
    )

    async def server_is_ready() -> bool:
        """Check if the server is ready.

        Returns:
            Whether the server is ready.
        """
        return_code, stdout, _ = await run_in_unit(unit, "curl http://localhost:8080")
        return return_code == 0 and bool(stdout)

    await wait_for(server_is_ready, timeout=30, check_interval=3)


async def setup_runner_with_repo_policy(
    app: Application,
    openstack_connection: openstack.connection.Connection,
    token: str,
    https_proxy: Optional[str],
) -> None:
    """Setup a runner with a local repo policy service.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        openstack_connection: OpenStack connection object.
        token: GitHub token.
        https_proxy: HTTPS proxy url to use.
    """
    unit = app.units[0]
    charm_token = secrets.token_hex(16)
    instance_helper = OpenStackInstanceHelper(openstack_connection)
    await app.set_config(
        {
            "repo-policy-compliance-token": charm_token,
            # Will remote port forward the service to the runner.
            "repo-policy-compliance-url": f"http://0.0.0.0:8080",
        }
    )

    await instance_helper.ensure_charm_has_runner(app=app)

    await instance_helper.install_repo_policy_in_instance(
        unit=unit, github_token=token, charm_token=charm_token, https_proxy=https_proxy
    )

    async def server_is_ready() -> bool:
        """Check if the server is ready.

        Returns:
            Whether the server is ready.
        """
        return_code, stdout, stderr = await instance_helper.run_in_instance(
            unit, "curl http://0.0.0.0:8080"
        )
        return return_code == 0

    await wait_for(server_is_ready, timeout=30, check_interval=3)
