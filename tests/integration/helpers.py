# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import json
from typing import Any

import juju.version
import yaml
from juju.action import Action
from juju.unit import Unit

from runner import Runner
from runner_manager import RunnerManager
from utilities import retry


async def check_runner_binary_exists(unit: Unit) -> bool:
    """Checks if runner binary exists in the charm.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        Whether the runner binary file exists in the charm.
    """
    action = await unit.run(f"test -f {RunnerManager.runner_bin_path}")
    await wait_on_action(action)
    return action.results["return-code"] == 0


async def get_repo_policy_compliance_pip_info(unit: Unit) -> None | str:
    """Get pip info for repo-policy-compliance.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        If repo-policy-compliance is installed, returns the pip show output, else returns none.
    """
    action = await unit.run("python3 -m pip show repo-policy-compliance")
    await wait_on_action(action)

    if action.results["return-code"] == 0:
        return action.results["stdout"]

    return None


async def install_repo_policy_compliance_from_git_source(unit: Unit, source: None | str) -> None:
    """Install repo-policy-compliance pip package from the git source.

    Args:
        unit: Unit instance to check for the LXD profile.
        source: The git source to install the package. If none the package is removed.
    """
    action = await unit.run("python3 -m pip uninstall --yes repo-policy-compliance")
    await wait_on_action(action)

    if source:
        action = await unit.run(f"python3 -m pip install {source}")
        await wait_on_action(action)

        assert action.results["return-code"] == 0


async def remove_runner_bin(unit: Unit) -> None:
    """Remove runner binary.

    Args:
        unit: Unit instance to check for the LXD profile.
    """
    action = await unit.run(f"rm {RunnerManager.runner_bin_path}")
    await wait_on_action(action)

    # No file should exists under with the filename.
    action = await unit.run(f"test -f {RunnerManager.runner_bin_path}")
    await wait_on_action(action)
    assert action.results["return-code"] != 0


async def assert_resource_lxd_profile(unit: Unit, configs: dict[str, Any]) -> None:
    """Check for LXD profile of the matching resource config.

    Args:
        unit: Unit instance to check for the LXD profile.
        configs: Configs of the application.

    Raises:
        AssertionError: Unable to find a LXD profile with matching resource
            config.
    """
    cpu = configs["vm-cpu"]["value"]
    mem = configs["vm-memory"]["value"]
    disk = configs["vm-disk"]["value"]
    resource_profile_name = Runner._get_resource_profile_name(cpu, mem, disk)

    # Verify the profile exists.
    action = await unit.run("lxc profile list --format json")
    await wait_on_action(action)
    assert action.results["return-code"] == 0
    profiles = json.loads(action.results["stdout"])
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    action = await unit.run(f"lxc profile show {resource_profile_name}")
    await wait_on_action(action)
    assert action.results["return-code"] == 0
    profile_content = yaml.safe_load(action.results["stdout"])
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
    action = await unit.run("lxc list --format json")
    await wait_on_action(action)

    assert action.results["return-code"] == 0

    lxc_instance: list[dict[str, str]] = json.loads(action.results["stdout"])
    return tuple(runner["name"] for runner in lxc_instance)


@retry(tries=30, delay=30)
async def assert_num_of_runners(unit: Unit, num: int) -> None:
    """Check if runner instances are ready.

    Args:
        unit: Unit instance to check for the LXD profile.
        num: Number of runner instances to check for.

    Raises:
        AssertionError: Correct number of runners is not found within timeout
            limit.
    """
    action = await unit.run("lxc list --format json")
    await wait_on_action(action)

    assert action.results["return-code"] == 0

    lxc_instance = json.loads(action.results["stdout"])
    assert (
        len(lxc_instance) == num
    ), f"Current number of runners: {len(lxc_instance)} Expected number of runner: {num}"

    for instance in lxc_instance:
        action = await unit.run(f"lxc exec {instance['name']} -- ps aux")
        await wait_on_action(action)
        assert action.status == "completed"

        assert f"/bin/bash {Runner.runner_script}" in action.results["stdout"]


async def wait_on_action(action: Action) -> None:
    """Wait on action if not juju 2.

    Since juju 3, actions needs to be await on.
    """
    # Prior to juju 3, the SUPPORTED_MAJOR_VERSION was not defined.
    if not hasattr(juju.version, "SUPPORTED_MAJOR_VERSION"):
        action.wait()
        return

    # Since juju 3, action.wait needs to be awaited on.
    await action.wait()
