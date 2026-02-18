# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""

from typing import AsyncIterator

import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.action import Action
from juju.application import Application
from juju.model import Model
from ops import ActiveStatus

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    get_job_logs,
    wait_for,
    wait_for_reconcile,
    wait_for_runner_ready,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    basic_app: Application,
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure the charm has no runner after a test.
    """
    yield basic_app

    await basic_app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await wait_for_reconcile(basic_app)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runner(app: Application, instance_helper: OpenStackInstanceHelper) -> None:
    """
    arrange: A working application with one runner.
    act: Run check_runner action.
    assert: Action returns result with one runner.
    """
    await instance_helper.set_app_runner_amount(app, 2)

    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "2"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"


# @pytest.mark.openstack
# @pytest.mark.asyncio
# @pytest.mark.abort_on_fail
# async def test_flush_runner_and_resource_config(
#     app: Application,
#     github_repository: Repository,
#     test_github_branch: Branch,
#     instance_helper: OpenStackInstanceHelper,
# ) -> None:
#     """
#     arrange: A working application with two runners.
#     act:
#         1. Run Check_runner action. Record the runner names for later.
#         2. Flush runners.
#         3. Dispatch a workflow to make runner busy and call flush_runner action.
#
#     assert:
#         1. Two runner exists.
#         2. Runners are recreated.
#         3. The runner is not flushed since by default it flushes idle.
#
#     Test are combined to reduce number of runner spawned.
#     """
#     await instance_helper.ensure_charm_has_runner(app)
#
#     # 1.
#     action: Action = await app.units[0].run_action("check-runners")
#     await action.wait()
#
#     assert action.status == "completed"
#     assert action.results["online"] == "1"
#     assert action.results["offline"] == "0"
#     assert action.results["unknown"] == "0"
#
#     runner_names = action.results["runners"].split(", ")
#     assert len(runner_names) == 1
#
#     # 2.
#     action = await app.units[0].run_action("flush-runners")
#     await action.wait()
#
#     await wait_for_runner_ready(app)
#
#     action = await app.units[0].run_action("check-runners")
#     await action.wait()
#
#     assert action.status == "completed"
#     assert action.results["online"] == "1"
#     assert action.results["offline"] == "0"
#     assert action.results["unknown"] == "0"
#
#     new_runner_names = action.results["runners"].split(", ")
#     assert len(new_runner_names) == 1
#     assert new_runner_names[0] != runner_names[0]
#
#     # 3.
#     workflow = await dispatch_workflow(
#         app=app,
#         branch=test_github_branch,
#         github_repository=github_repository,
#         conclusion="success",
#         workflow_id_or_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
#         dispatch_input={"runner": app.name, "minutes": "5"},
#         wait=False,
#     )
#     await wait_for(lambda: workflow.update() or workflow.status == "in_progress")
#     action = await app.units[0].run_action("flush-runners")
#     await action.wait()
#
#     assert action.status == "completed"
#
#
# @pytest.mark.openstack
# @pytest.mark.asyncio
# @pytest.mark.abort_on_fail
# async def test_custom_pre_job_script(
#     app: Application,
#     github_repository: Repository,
#     test_github_branch: Branch,
# ) -> None:
#     """
#     arrange: A working application with one runner with a custom pre-job script enabled.
#     act: Dispatch a workflow.
#     assert: Workflow run successfully passed and pre-job script has been executed.
#     """
#     await app.set_config(
#         {
#             BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
#             CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME: """
# #!/usr/bin/env bash
# cat > ~/.ssh/config <<EOF
# host github.com
#   user git
#   hostname github.com
#   port 22
#   proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128
# EOF
# logger -s "SSH config: $(cat ~/.ssh/config)"
#     """,
#         }
#     )
#     await wait_for_runner_ready(app)
#
#     workflow_run = await dispatch_workflow(
#         app=app,
#         branch=test_github_branch,
#         github_repository=github_repository,
#         conclusion="success",
#         workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
#         dispatch_input={"runner": app.name},
#     )
#     logs = get_job_logs(workflow_run.jobs("latest")[0])
#     assert "SSH config" in logs
#     assert "proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128" in logs


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_planner_pressure_spawns_and_cleans_single_runner(
    model: Model,
    app: Application,
    mock_planner_http_app: Application,
    mock_planner_http_unit_ip: str,
    planner_token_secret_name: str,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working runner app, a HTTP planner app, and planner secret grant.
    act:
        1. Set base-virtual-machines to 0 and relate planner.
        2. Change planner pressure from 1 to 0 through control endpoint.
        3. Remove planner relation.
    assert:
        1. Planner drives runner count from 0 to 1.
        2. Planner pressure 0 drives runner count back to 0.
        3. App returns to active after relation removal.
    """
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await model.grant_secret(planner_token_secret_name, app.name)
    await model.relate(f"{app.name}:planner", mock_planner_http_app.name)
    await model.wait_for_idle(
        apps=[app.name, mock_planner_http_app.name],
        status=ActiveStatus.name,
        idle_period=30,
        timeout=10 * 60,
    )

    unit = app.units[0]

    async def _runner_count(number: int) -> bool:
        return len(await instance_helper.get_runner_names(unit)) == number

    await wait_for(lambda: _runner_count(1), timeout=10 * 60, check_interval=10)

    response = requests.post(
        f"http://{mock_planner_http_unit_ip}:8080/control/pressure",
        json={"pressure": 0},
        timeout=30,
    )
    assert response.status_code == 200

    await wait_for(lambda: _runner_count(0), timeout=15 * 60, check_interval=15)

    await mock_planner_http_app.remove_relation(
        "provide-github-runner-planner-v0",
        f"{app.name}:planner",
    )
    await model.wait_for_idle(
        apps=[app.name],
        status=ActiveStatus.name,
        idle_period=30,
        timeout=10 * 60,
    )
