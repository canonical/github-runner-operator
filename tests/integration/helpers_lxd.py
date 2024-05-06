#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json

from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers import run_in_unit, wait_till_num_of_runners, reconcile


async def run_in_instance(
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


async def ensure_charm_has_runner(app: Application, model: Model) -> None:
    """Reconcile the charm to contain one runner.

    Args:
        app: The GitHub Runner Charm app to create the runner for.
        model: The machine charm model.
    """
    await set_app_runner_amount(app, model, 1)


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