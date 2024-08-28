#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics/logs assuming Github workflow failures or a runner crash."""
import time
from asyncio import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from metrics import runner_logs
from metrics.runner import PostJobStatus

from charm_state import PATH_CONFIG_NAME, VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    assert_events_after_reconciliation,
    cancel_workflow_run,
    clear_metrics_log,
    print_loop_device_info,
    wait_for_runner_to_be_marked_offline,
    wait_for_workflow_to_start,
)
from tests.integration.helpers.common import (
    DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    InstanceHelper,
    dispatch_workflow,
    reconcile,
    run_in_unit,
)
from tests.integration.helpers.lxd import (
    ensure_charm_has_runner,
    get_runner_name,
    run_in_lxd_instance,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, setup_repo_policy


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model, app_for_metric: Application, loop_device: str
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_for_metric.units[0]
    await clear_metrics_log(unit)
    await print_loop_device_info(unit, loop_device)
    await app_for_metric.set_config(
        {
            VIRTUAL_MACHINES_CONFIG_NAME: "0",
            "repo-policy-compliance-token": "",
            "repo-policy-compliance-url": "",
        }
    )
    await reconcile(app=app_for_metric, model=model)

    yield app_for_metric


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_for_failed_repo_policy(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
    token: str,
    https_proxy: str,
    instance_helper: InstanceHelper,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow that fails the repo-policy check. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to failure.
    """
    await app.set_config({PATH_CONFIG_NAME: forked_github_repository.full_name})

    # TODO: debug
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(instance_helper)
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    if isinstance(instance_helper, OpenStackInstanceHelper):
        await setup_repo_policy(
            app=app,
            openstack_connection=instance_helper.openstack_connection,
            token=token,
            https_proxy=https_proxy,
        )
    else:
        await instance_helper.ensure_charm_has_runner(app)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await clear_metrics_log(unit)
    await dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="failure",
        workflow_id_or_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config(
        {
            VIRTUAL_MACHINES_CONFIG_NAME: "0",
        }
    )
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app,
        github_repository=forked_github_repository,
        post_job_status=PostJobStatus.REPO_POLICY_CHECK_FAILURE,
    )


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_for_abnormal_termination(
    model: Model,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    instance_helper: InstanceHelper,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow and afterwards kill run.sh. After that, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to Abnormal.
    """
    await app.set_config({PATH_CONFIG_NAME: github_repository.full_name})
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await instance_helper.ensure_charm_has_runner(app)

    unit = app.units[0]

    workflow = github_repository.get_workflow(
        id_or_file_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME
    )
    dispatch_time = time.time()
    assert workflow.create_dispatch(test_github_branch, {"runner": app.name})

    await wait_for_workflow_to_start(
        unit,
        workflow,
        branch=test_github_branch,
        started_time=dispatch_time,
        instance_helper=instance_helper,
    )

    # Wait a bit to ensure pre-job script has been executed.
    await sleep(10)

    # Make the runner terminate abnormally by killing run.sh
    runner_name = await instance_helper.get_runner_name(unit)
    kill_run_sh_cmd = "pkill -9 run.sh"
    ret_code, stdout, stderr = await instance_helper.run_in_instance(unit, kill_run_sh_cmd)
    assert ret_code == 0, f"Failed to kill run.sh with code {ret_code}: {stderr}"

    # Cancel workflow and wait that the runner is marked offline
    # to avoid errors during reconciliation.
    await cancel_workflow_run(
        unit, workflow, branch=test_github_branch, instance_helper=instance_helper
    )
    await wait_for_runner_to_be_marked_offline(github_repository, runner_name)

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app,
        github_repository=github_repository,
        post_job_status=PostJobStatus.ABNORMAL,
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_retrieves_logs_from_unhealthy_runners(
    model: Model,
    app: Application,
):
    """
    arrange: A properly integrated charm with one runner.
    act: Kill the start.sh script, which marks the runner as unhealthy. After that, reconcile.
    assert: The logs are pulled from the crashed runner.
    """
    await ensure_charm_has_runner(app=app, model=model)

    unit = app.units[0]
    runner_name = await get_runner_name(unit)

    kill_start_sh_cmd = "pkill -9 start.sh"
    ret_code, stdout, stderr = await run_in_lxd_instance(unit, runner_name, kill_start_sh_cmd)
    assert ret_code == 0, f"Failed to kill start.sh, {stdout} {stderr}"

    # Set the number of virtual machines to 0 to avoid to speedup reconciliation.
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app=app, model=model)

    ret_code, stdout, stderr = await run_in_unit(unit, f"ls {runner_logs.RUNNER_LOGS_DIR_PATH}")
    assert ret_code == 0, f"Failed to list crashed runner logs {stdout} {stderr}"
    assert stdout
    assert runner_name in stdout, "Failed to find crashed runner log"

    ret_code, stdout, _ = await run_in_unit(
        unit, f"ls {runner_logs.RUNNER_LOGS_DIR_PATH}/{runner_name}"
    )
    assert ret_code == 0, "Failed to list crashed runner log"
    assert stdout
    assert "_diag" in stdout, "Failed to find crashed runner diag log"
    assert "syslog" in stdout, "Failed to find crashed runner syslog log"
