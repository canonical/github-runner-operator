#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import logging
from typing import Any

import yaml
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from runner import Runner
from tests.integration.helpers.common import InstanceHelper, reconcile, run_in_unit, wait_for

logger = logging.getLogger(__name__)


class LXDInstanceHelper(InstanceHelper):
    """Helper class to interact with LXD instances."""

    async def run_in_instance(
        self, unit: Unit, command: str, timeout: int | None = None
    ) -> tuple[int, str | None, str | None]:
        """Run command in LXD instance.

        Args:
            unit: Juju unit to execute the command in.
            command: Command to execute.
            timeout: Amount of time to wait for the execution.

        Returns:
            Tuple of return code, stdout and stderr.
        """
        name = await self.get_runner_name(unit)
        return await run_in_lxd_instance(unit, name, command, timeout=timeout)

    async def ensure_charm_has_runner(self, app: Application):
        """Reconcile the charm to contain one runner.

        Args:
            app: The GitHub Runner Charm app to create the runner for.
        """
        await ensure_charm_has_runner(app, app.model)

    async def get_runner_name(self, unit: Unit) -> str:
        """Get the name of the runner.

        Expects only one runner to be present.

        Args:
            unit: The GitHub Runner Charm unit to get the runner name for.

        Returns:
            The Github runner name deployed in the given unit.
        """
        return await get_runner_name(unit)


async def assert_resource_lxd_profile(unit: Unit, configs: dict[str, Any]) -> None:
    """Check for LXD profile of the matching resource config.

    Args:
        unit: Unit instance to check for the LXD profile.
        configs: Configs of the application.
    """
    cpu = configs["vm-cpu"]["value"]
    mem = configs["vm-memory"]["value"]
    disk = configs["vm-disk"]["value"]
    resource_profile_name = Runner._get_resource_profile_name(cpu, mem, disk)

    # Verify the profile exists.
    return_code, stdout, _ = await run_in_unit(unit, "lxc profile list --format json")
    assert return_code == 0
    assert stdout is not None
    profiles = json.loads(stdout)
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    return_code, stdout, _ = await run_in_unit(unit, f"lxc profile show {resource_profile_name}")
    assert return_code == 0
    assert stdout is not None
    profile_content = yaml.safe_load(stdout)
    assert f"{cpu}" == profile_content["config"]["limits.cpu"]
    assert mem == profile_content["config"]["limits.memory"]
    assert disk == profile_content["devices"]["root"]["size"]


async def get_runner_names(unit: Unit) -> tuple[str, ...]:
    """Get names of the runners in LXD.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        Tuple of runner names.
    """
    return_code, stdout, _ = await run_in_unit(unit, "lxc list --format json")

    assert return_code == 0
    assert stdout is not None

    lxc_instance: list[dict[str, str]] = json.loads(stdout)
    return tuple(runner["name"] for runner in lxc_instance if runner["name"] != "builder")


async def wait_till_num_of_runners(unit: Unit, num: int, timeout: int = 10 * 60) -> None:
    """Wait and check the number of runners.

    Args:
        unit: Unit instance to check for the LXD profile.
        num: Number of runner instances to check for.
        timeout: Number of seconds to wait for the runners.
    """

    async def get_lxc_instances() -> None | list[dict]:
        """Get lxc instances list info.

        Returns:
            List of lxc instance dictionaries, None if failed to get list.
        """
        return_code, stdout, _ = await run_in_unit(unit, "lxc list --format json")
        if return_code != 0 or not stdout:
            logger.error("Failed to run lxc list, %s", return_code)
            return None
        return json.loads(stdout)

    async def is_desired_num_runners():
        """Return whether there are desired number of lxc instances running.

        Returns:
            Whether the desired number of lxc runners have been reached.
        """
        lxc_instances = await get_lxc_instances()
        if lxc_instances is None:
            return False
        return len(lxc_instances) == num

    await wait_for(is_desired_num_runners, timeout=timeout, check_interval=30)

    instances = await get_lxc_instances()
    if not instances:
        return

    for instance in instances:
        return_code, stdout, _ = await run_in_unit(unit, f"lxc exec {instance['name']} -- ps aux")
        assert return_code == 0

        assert stdout is not None
        assert f"/bin/bash {Runner.runner_script}" in stdout


async def run_in_lxd_instance(
    unit: Unit,
    name: str,
    command: str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: int | None = None,
) -> tuple[int, str | None, str | None]:
    """Run command in LXD instance of a juju unit.

    Args:
        unit: Juju unit to execute the command in.
        name: Name of LXD instance.
        command: Command to execute.
        env: Mapping of environment variable name to value.
        cwd: Work directory of the command.
        timeout: Amount of time to wait for the execution.

    Returns:
        Tuple of return code and stdout.
    """
    lxc_cmd = f"/snap/bin/lxc exec {name}"
    if env:
        for key, value in env.items():
            lxc_cmd += f"--env {key}={value}"
    if cwd:
        lxc_cmd += f" --cwd {cwd}"
    lxc_cmd += f" -- {command}"
    return await run_in_unit(unit, lxc_cmd, timeout)


async def start_test_http_server(unit: Unit, port: int):
    """Start test http server.

    Args:
        unit: The unit to start the test server in.
        port: Http server port.
    """
    await run_in_unit(
        unit,
        f"""cat <<EOT > /etc/systemd/system/test-http-server.service
[Unit]
Description=Simple HTTP server for testing
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu
ExecStart=python3 -m http.server {port}
EOT""",
    )
    await run_in_unit(unit, "/usr/bin/systemctl daemon-reload")
    await run_in_unit(unit, "/usr/bin/systemctl start test-http-server")

    async def server_is_ready() -> bool:
        """Check if the server is ready.

        Returns:
            Whether the server is ready.
        """
        return_code, stdout, _ = await run_in_unit(unit, f"curl http://localhost:{port}")
        return return_code == 0 and bool(stdout)

    await wait_for(server_is_ready, timeout=30, check_interval=3)


async def set_app_runner_amount(app: Application, model: Model, num_runners: int) -> None:
    """Reconcile the application to a runner amount.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
        num_runners: The number of runners.
    """
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: f"{num_runners}"})
    await reconcile(app=app, model=model)
    await wait_till_num_of_runners(unit=app.units[0], num=num_runners)


async def ensure_charm_has_runner(app: Application, model: Model) -> None:
    """Reconcile the charm to contain one runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
    """
    await set_app_runner_amount(app, model, 1)


async def get_runner_name(unit: Unit) -> str:
    """Get the name of the runner.

    Expects only one runner to be present.

    Args:
        unit: The GitHub Runner Charm unit to get the runner name for.

    Returns:
        The Github runner name deployed in the given unit.
    """
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    return runners[0]
