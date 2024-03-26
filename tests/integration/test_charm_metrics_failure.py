#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics/logs assuming Github workflow failures or a runner crash."""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

import runner_logs
from runner_metrics import PostJobStatus
from tests.integration.charm_metrics_helpers import (
    assert_events_after_reconciliation,
    cancel_workflow_run,
    clear_metrics_log,
    print_loop_device_info,
    wait_for_runner_to_be_marked_offline,
    wait_for_workflow_to_start,
)
from tests.integration.helpers import (
    DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    ensure_charm_has_runner,
    get_runner_name,
    reconcile,
    run_in_lxd_instance,
    run_in_unit,
)


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model, app_with_grafana_agent: Application, loop_device: str
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_with_grafana_agent.units[0]
    await clear_metrics_log(unit)
    await print_loop_device_info(unit, loop_device)
    yield app_with_grafana_agent


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_for_failed_repo_policy(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow that fails the repo-policy check. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to failure.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

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
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app,
        github_repository=forked_github_repository,
        post_job_status=PostJobStatus.REPO_POLICY_CHECK_FAILURE,
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_for_abnormal_termination(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow and afterwards kill run.sh. After that, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to Abnormal.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    unit = app.units[0]

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME
    )
    assert workflow.create_dispatch(forked_github_branch, {"runner": app.name})

    await wait_for_workflow_to_start(unit, workflow, branch=forked_github_branch)

    # Make the runner terminate abnormally by killing run.sh
    runner_name = await get_runner_name(unit)
    kill_run_sh_cmd = "pkill -9 run.sh"
    ret_code, _ = await run_in_lxd_instance(unit, runner_name, kill_run_sh_cmd)
    assert ret_code == 0, "Failed to kill run.sh"

    # Cancel workflow and wait that the runner is marked offline
    # to avoid errors during reconciliation.
    await cancel_workflow_run(unit, workflow)
    await wait_for_runner_to_be_marked_offline(forked_github_repository, runner_name)

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await assert_events_after_reconciliation(
        app=app,
        github_repository=forked_github_repository,
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
    ret_code, _ = await run_in_lxd_instance(unit, runner_name, kill_start_sh_cmd)
    assert ret_code == 0, "Failed to kill start.sh"

    # Set the number of virtual machines to 0 to avoid to speedup reconciliation.
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    ret_code, stdout = await run_in_unit(unit, f"ls {runner_logs.CRASHED_RUNNER_LOGS_DIR_PATH}")
    assert ret_code == 0, "Failed to list crashed runner logs"
    assert stdout
    assert runner_name in stdout, "Failed to find crashed runner log"

    ret_code, stdout = await run_in_unit(
        unit, f"ls {runner_logs.CRASHED_RUNNER_LOGS_DIR_PATH}/{runner_name}"
    )
    assert ret_code == 0, "Failed to list crashed runner log"
    assert stdout
    assert "_diag" in stdout, "Failed to find crashed runner diag log"
    assert "syslog" in stdout, "Failed to find crashed runner syslog log"
