# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import pytest

log = logging.getLogger(__name__)


async def file_contents(unit, path):
    cmd = "cat {}".format(path)
    action = await unit.run(cmd)
    return action.results["Stdout"]


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    my_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(my_charm)
    await ops_test.model.wait_for_idle()


async def test_status(units):
    assert units[0].workload_status == "blocked"
    assert units[0].workload_status_message == "Missing token or org/repo path config"
