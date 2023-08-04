# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import json
from typing import Any

import yaml
from juju.unit import Unit

from runner import Runner
from runner_manager import RunnerManager
from utilities import retry


async def get_repo_policy_compliance_pip_info(unit: Unit) -> None | str:
    """Get pip info for repo-policy-compliance.

    Args:
        source: The git source to install the package. If none the package is removed.
    """
    action = await unit.run("pip show repo-policy-compliance")
    await action.wait()

    if action.results["return-code"] == 0:
        return action.results["stdout"]

    return None


async def install_repo_policy_compliance_from_git_source(unit: Unit, source: None | str) -> None:
    """Install repo-policy-compliance pip package from the git source.

    Args:
        source: The git source to install the package. If none the package is removed.
    """
    action = await unit.run("pip uninstall --yes repo-policy-compliance")
    await action.wait()

    if source:
        action = await unit.run(f"pip install {source}")
        await action.wait()

        assert action.results["return-code"] == 0


async def remove_runner_bin(unit: Unit) -> None:
    """Remove runner binary.

    Args:
        unit: Unit instance to check for the LXD profile.
    """
    action = await unit.run(f"rm {RunnerManager.runner_bin_path}")
    await action.wait()

    # No file should exists under with the filename.
    action = await unit.run(f"test -f {RunnerManager.runner_bin_path}")
    await action.wait()
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
    await action.wait()
    assert action.results["return-code"] == 0
    profiles = json.loads(action.results["stdout"])
    profile_names = [profile["name"] for profile in profiles]
    assert resource_profile_name in profile_names

    # Verify the profile contains the correct resource settings.
    action = await unit.run(f"lxc profile show {resource_profile_name}")
    await action.wait()
    assert action.results["return-code"] == 0
    profile_content = yaml.safe_load(action.results["stdout"])
    assert f"{cpu}" == profile_content["config"]["limits.cpu"]
    assert mem == profile_content["config"]["limits.memory"]
    assert disk == profile_content["devices"]["root"]["size"]


@retry(tries=30, delay=30)
async def assesrt_num_of_runners(unit: Unit, num: int) -> None:
    """Check if runner instances are ready.

    Args:
      app: Application instance to check the runners.
      num: Number of runner instances to check for.

    Raises:
        AssertionError: Correct number of runners is not found within timeout
            limit.
    """
    action = await unit.run("lxc list --format json")
    await action.wait()
    assert action.status == "completed"

    assert action.results["return-code"] == 0

    lxc_instance = json.loads(action.results["stdout"])
    assert len(lxc_instance) == num

    for instance in lxc_instance:
        action = await unit.run(f"lxc exec {instance['name']} -- ps aux")
        await action.wait()
        assert action.status == "completed"

        assert f"/bin/bash {Runner.runner_script}" in action.results["stdout"]
