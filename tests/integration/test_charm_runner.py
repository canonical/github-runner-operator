# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.action import Action
from juju.application import Application
from juju.model import Model

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    get_job_logs,
    wait_for_reconcile,
    wait_for,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, setup_repo_policy


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model,
    basic_app: Application,
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Ensure the charm has no runner after a test.
    """
    yield basic_app

    await basic_app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await wait_for_reconcile(basic_app, basic_app.model)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runner(app: Application, instance_helper: OpenStackInstanceHelper) -> None:
    """
    arrange: A working application with one runner.
    act: Run check_runner action.
    assert: Action returns result with one runner.
    """
    await instance_helper.ensure_charm_has_runner(app)
    await wait_for_reconcile(app, app.model)

    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_flush_runner_and_resource_config(
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with one runner.
    act:
        1. Run Check_runner action. Record the runner name for later.
        2. Nothing.
        3. Change the virtual machine resource configuration.
        4. Run flush_runner action.
        5. Dispatch a workflow to make runner busy and call flush_runner action.

    assert:
        1. One runner exists.
        2. Check the resource matches the configuration.
        3. The runner is not flushed since by default it flushes idle.

    Test are combined to reduce number of runner spawned.
    """
    await instance_helper.ensure_charm_has_runner(app)
    await wait_for_reconcile(app, app.model)

    # 1.
    action: Action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    runner_names = action.results["runners"].split(", ")
    assert len(runner_names) == 1

    # 2.
    action = await app.units[0].run_action("flush-runners")
    await action.wait()

    # There is a race condition in here. When deleting a runner in openstack, it can take
    # a while to get the runner deleted and the "flush-runner" will not spawn a new runner.
    # We may need to call flush-runners twice and wait in the middle until the openstack
    # instance disappear.

    action = await app.units[0].run_action("check-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["online"] == "1"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"

    new_runner_names = action.results["runners"].split(", ")
    assert len(new_runner_names) == 1
    assert new_runner_names[0] != runner_names[0]

    # 3.
    workflow = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": app.name, "minutes": "5"},
        wait=False,
    )
    await wait_for(lambda: workflow.update() or workflow.status == "in_progress")
    action = await app.units[0].run_action("flush-runners")
    await action.wait()

    assert action.status == "completed"
    assert action.results["delta"]["virtual-machines"] == "0"


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_custom_pre_job_script(
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    token: str,
    https_proxy: str,
) -> None:
    """
    arrange: A working application with one runner with a custom pre-job script enabled.
    act: Dispatch a workflow.
    assert: Workflow run successfully passed and pre-job script has been executed.
    """
    await app.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME: """
#!/usr/bin/env bash
cat > ~/.ssh/config <<EOF
host github.com
  user git
  hostname github.com
  port 22
  proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128
EOF
logger -s "SSH config: $(cat ~/.ssh/config)"
    """,
        }
    )
    await wait_for_reconcile(app, app.model)

    workflow_run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": app.name},
    )
    logs = get_job_logs(workflow_run.jobs("latest")[0])
    assert "SSH config" in logs
    assert "proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128" in logs


# WARNING: the test below sets up repo policy which affects all tests coming after it. It should
# be the last test in the file.
@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_repo_policy_enabled(
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    token: str,
    https_proxy: str,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with one runner with repo policy enabled.
    act: Dispatch a workflow.
    assert: Workflow run successfully passed.
    """
    await setup_repo_policy(
        app=app,
        openstack_connection=instance_helper.openstack_connection,
        token=token,
        https_proxy=https_proxy,
    )

    await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
    )
