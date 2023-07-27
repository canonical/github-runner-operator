# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for integration test."""

import json

from juju.unit import Unit

from runner import Runner
from runner_manager import RunnerManager
from utilities import retry


async def remove_runner_bin(unit: Unit):
    action = await unit.run(f"rm {RunnerManager.runner_bin_path}")
    await action.wait()

    # No file should exists under with the filename.
    action = await unit.run(f"test -f {RunnerManager.runner_bin_path}")
    await action.wait()
    assert action.results["return-code"] != 0


@retry(tries=30, delay=30)
async def check_runner_instance(unit: Unit, num: int) -> None:
    """Helper function to wait for runner instances to be ready.

    Args:
      app: Application instance to check the runners.
      num: Number of runner instances to check for.
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
