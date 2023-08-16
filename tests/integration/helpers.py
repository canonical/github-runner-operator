# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import json
from typing import Any

import juju.version
import yaml
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
    return_code, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    return return_code == 0


async def get_repo_policy_compliance_pip_info(unit: Unit) -> None | str:
    """Get pip info for repo-policy-compliance.

    Args:
        unit: Unit instance to check for the LXD profile.

    Returns:
        If repo-policy-compliance is installed, returns the pip show output, else returns none.
    """
    return_code, stdout = await run_in_unit(unit, "python3 -m pip show repo-policy-compliance")

    if return_code == 0:
        return stdout

    return None


async def install_repo_policy_compliance_from_git_source(unit: Unit, source: None | str) -> None:
    """Install repo-policy-compliance pip package from the git source.

    Args:
        unit: Unit instance to check for the LXD profile.
        source: The git source to install the package. If none the package is removed.
    """
    await run_in_unit(unit, "python3 -m pip uninstall --yes repo-policy-compliance")

    if source:
        return_code, _ = await run_in_unit(unit, f"python3 -m pip install {source}")
        assert return_code == 0


async def remove_runner_bin(unit: Unit) -> None:
    """Remove runner binary.

    Args:
        unit: Unit instance to check for the LXD profile.
    """
    await run_in_unit(unit, f"rm {RunnerManager.runner_bin_path}")

    # No file should exists under with the filename.
    return_code, _ = await run_in_unit(unit, f"test -f {RunnerManager.runner_bin_path}")
    assert return_code != 0


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
    return_code, stdout = await run_in_unit(unit, "lxc profile list --format json")
    assert return_code == 0
    profiles = json.loads(stdout)
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    return_code, stdout = await run_in_unit(unit, f"lxc profile show {resource_profile_name}")
    assert return_code == 0
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
    return_code, stdout = await run_in_unit(unit, "lxc list --format json")

    assert return_code == 0

    lxc_instance: list[dict[str, str]] = json.loads(stdout)
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
    return_code, stdout = await run_in_unit(unit, "lxc list --format json")
    assert return_code == 0

    lxc_instance = json.loads(stdout)
    assert (
        len(lxc_instance) == num
    ), f"Current number of runners: {len(lxc_instance)} Expected number of runner: {num}"

    for instance in lxc_instance:
        return_code, stdout = await run_in_unit(unit, f"lxc exec {instance['name']} -- ps aux")
        assert return_code == 0

        assert f"/bin/bash {Runner.runner_script}" in stdout


async def run_in_unit(unit: Unit, command: str, timeout=None) -> tuple[int, str | None]:
    """Run command in juju unit.

    Compatible with juju 3 and juju 2.

    Args:
        unit: Juju unit to execute the command in.
        command: Command to execute.

    Returns:
        Tuple of return code and stdout.
    """
    action = await unit.run(command, timeout)

    # For compatibility with juju 2.
    # Prior to juju 3, the SUPPORTED_MAJOR_VERSION was not defined.
    if not hasattr(juju.version, "SUPPORTED_MAJOR_VERSION"):
        return (int(action.results["Code"]), action.results.get("Stdout", None))

    await action.wait()
    return (action.results["return-code"], action.results.get("stdout", None))
