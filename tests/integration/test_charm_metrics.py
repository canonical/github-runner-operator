# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics/logs."""
import json
import logging
from datetime import datetime, timezone
from time import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

import runner_logs
from github_type import JobConclusion
from metrics import METRICS_LOG_PATH
from runner_metrics import PostJobStatus
from tests.integration.helpers import (
    DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
    DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_name,
    get_runner_names,
    reconcile,
    run_in_lxd_instance,
    run_in_unit,
)
from tests.status_name import ACTIVE

TEST_WORKFLOW_NAMES = [
    "Workflow Dispatch Tests",
    "Workflow Dispatch Crash Tests",
    "Workflow Dispatch Failure Tests 2a34f8b1-41e4-4bcb-9bbf-7a74e6c482f7",
]
JOB_LOG_START_MSG_TEMPLATE = "Job is about to start running on the runner: {runner_name}"


@pytest_asyncio.fixture(scope="module", name="app_integrated")
async def app_integrated_fixture(
    model: Model, app_no_runner: Application
) -> AsyncIterator[Application]:
    """Setup the charm to be integrated with grafana-agent using the cos-agent integration."""
    await _integrate_apps(app_no_runner, model)

    yield app_no_runner


async def _clear_metrics_log(unit: Unit) -> None:
    """Clear the metrics log on the unit.

    Args:
        unit: The unit to clear the metrics log on.
    """
    retcode, _ = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then rm {METRICS_LOG_PATH}; fi",
    )
    assert retcode == 0, "Failed to clear metrics log"


async def _print_loop_device_info(unit: Unit, loop_device: str) -> None:
    """Print loop device info on the unit.

    Args:
        unit: The unit to print the loop device info on.
        loop_device: The loop device to print the info for.
    """
    retcode, stdout = await run_in_unit(
        unit=unit,
        command="sudo losetup -lJ",
    )
    assert retcode == 0, f"Failed to get loop devices: {stdout}"
    assert stdout is not None, "Failed to get loop devices, no stdout message"
    loop_devices_info = json.loads(stdout)
    for loop_device_info in loop_devices_info["loopdevices"]:
        if loop_device_info["name"] == loop_device:
            logging.info("Loop device %s info: %s", loop_device, loop_device_info)
            break
    else:
        logging.info("Loop device %s not found", loop_device)


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    model: Model, app_integrated: Application, loop_device: str
) -> AsyncIterator[Application]:
    """Setup and teardown the charm after each test.

    Clear the metrics log before each test.
    """
    unit = app_integrated.units[0]
    await _clear_metrics_log(unit)
    await _print_loop_device_info(unit, loop_device)
    yield app_integrated


async def _get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    retcode, stdout = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then cat {METRICS_LOG_PATH}; else echo ''; fi",
    )
    assert retcode == 0, f"Failed to get metrics log: {stdout}"
    assert stdout is not None, "Failed to get metrics log, no stdout message"
    logging.info("Metrics log: %s", stdout)
    return stdout.strip()


async def _integrate_apps(app: Application, model: Model):
    """Integrate the charm with grafana-agent using the cos-agent integration.

    Args:
        app: The charm to integrate.
        model: The model to deploy the grafana-agent to.
    """
    grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status=ACTIVE)
    await model.wait_for_idle(apps=[grafana_agent.name])


async def _wait_until_runner_is_used_up(runner_name: str, unit: Unit):
    """Wait until the runner is used up.

    Args:
        runner_name: The runner name to wait for.
        unit: The unit which contains the runner.
    """
    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner_name not in runners:
            break
        sleep(30)
    else:
        assert False, "Timeout while waiting for the runner to be used up"


async def _assert_workflow_run_conclusion(
    runner_name: str, conclusion: str, workflow: Workflow, start_time: datetime
):
    """Assert that the workflow run has the expected conclusion.

    Args:
        runner_name: The runner name to assert the workflow run conclusion for.
        conclusion: The expected workflow run conclusion.
        workflow: The workflow to assert the workflow run conclusion for.
        start_time: The start time of the workflow.
    """
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if JOB_LOG_START_MSG_TEMPLATE.format(runner_name=runner_name) in logs:
            assert run.jobs()[0].conclusion == conclusion


async def _wait_for_workflow_to_complete(
    unit: Unit, workflow: Workflow, conclusion: str, start_time: datetime
):
    """Wait for the workflow to complete.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to wait for.
        conclusion: The workflow conclusion to wait for.
        start_time: The start time of the workflow.
    """
    runner_name = await get_runner_name(unit)
    await _wait_until_runner_is_used_up(runner_name, unit)
    # Wait for the workflow log to contain the conclusion
    sleep(60)

    await _assert_workflow_run_conclusion(
        runner_name=runner_name, conclusion=conclusion, workflow=workflow, start_time=start_time
    )


async def _wait_for_workflow_to_start(unit: Unit, workflow: Workflow):
    """Wait for the workflow to start.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to wait for.
    """
    runner_name = await get_runner_name(unit)
    for _ in range(30):
        for run in workflow.get_runs():
            jobs = run.jobs()
            if jobs:
                logs_url = jobs[0].logs_url()
                logs = requests.get(logs_url).content.decode("utf-8")

                if JOB_LOG_START_MSG_TEMPLATE.format(runner_name=runner_name) in logs:
                    break
        else:
            sleep(30)
            continue
        break
    else:
        assert False, "Timeout while waiting for the workflow to start"


async def _cancel_workflow_run(unit: Unit, workflow: Workflow):
    """Cancel the workflow run.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to cancel the workflow run for.
    """
    runner_name = await get_runner_name(unit)

    for run in workflow.get_runs():
        jobs = run.jobs()
        if jobs:
            logs_url = jobs[0].logs_url()
            logs = requests.get(logs_url).content.decode("utf-8")

            if JOB_LOG_START_MSG_TEMPLATE.format(runner_name=runner_name) in logs:
                run.cancel()


async def _dispatch_workflow(
    app: Application, branch: Branch, github_repository: Repository, conclusion: str
):
    """Dispatch a workflow on a branch for the runner to run.

    The function assumes that there is only one runner running in the unit.

    Args:
        app: The charm to dispatch the workflow for.
        branch: The branch to dispatch the workflow on.
        github_repository: The github repository to dispatch the workflow on.
        conclusion: The expected workflow run conclusion.
    """
    start_time = datetime.now(timezone.utc)

    workflow = github_repository.get_workflow(id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME)
    if conclusion == "failure":
        workflow = github_repository.get_workflow(
            id_or_file_name=DISPATCH_FAILURE_TEST_WORKFLOW_FILENAME
        )

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(branch, {"runner": app.name})
    await _wait_for_workflow_to_complete(
        unit=app.units[0], workflow=workflow, conclusion=conclusion, start_time=start_time
    )


async def _assert_events_after_reconciliation(
    app: Application, github_repository: Repository, post_job_status: PostJobStatus
):
    """Assert that the RunnerStart, RunnerStop and Reconciliation metric is logged.

    Args:
        app: The charm to assert the events for.
        github_repository: The github repository to assert the events for.
        post_job_status: The expected post job status of the reconciliation event.
    """
    unit = app.units[0]

    metrics_log = await _get_metrics_log(unit=unit)
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    events = set(map(lambda line: line.get("event"), log_lines))
    assert {
        "runner_start",
        "runner_stop",
        "reconciliation",
    } <= events, "Not all events were logged"
    for metric_log in log_lines:
        if metric_log.get("event") == "runner_start":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("workflow") in TEST_WORKFLOW_NAMES
            assert metric_log.get("repo") == github_repository.full_name
            assert metric_log.get("github_event") == "workflow_dispatch"
            assert metric_log.get("idle") >= 0
            assert metric_log.get("queue_duration") >= 0
        if metric_log.get("event") == "runner_stop":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("workflow") in TEST_WORKFLOW_NAMES
            assert metric_log.get("repo") == github_repository.full_name
            assert metric_log.get("github_event") == "workflow_dispatch"
            assert metric_log.get("status") == post_job_status
            if post_job_status == PostJobStatus.ABNORMAL:
                assert metric_log.get("status_info", {}).get("code", 0) != 0
                # Either the job conclusion is not yet set or it is set to cancelled.
                assert metric_log.get("job_conclusion") in [
                    None,
                    JobConclusion.CANCELLED,
                ]
            elif post_job_status == PostJobStatus.REPO_POLICY_CHECK_FAILURE:
                assert metric_log.get("status_info", {}).get("code", 0) == 403
                assert metric_log.get("job_conclusion") == JobConclusion.FAILURE
            else:
                assert "status_info" not in metric_log
                assert metric_log.get("job_conclusion") == JobConclusion.SUCCESS
            assert metric_log.get("job_duration") >= 0
        if metric_log.get("event") == "reconciliation":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("duration") >= 0
            assert metric_log.get("crashed_runners") == 0
            assert metric_log.get("idle_runners") >= 0


async def _wait_for_runner_to_be_marked_offline(
    forked_github_repository: Repository, runner_name: str
):
    """Wait for the runner to be marked offline or to be non-existent.

    Args:
        forked_github_repository: The github repository to wait for the runner
        to be marked offline.
        runner_name: The runner name to wait for.
    """
    for _ in range(30):
        for runner in forked_github_repository.get_self_hosted_runners():
            if runner.name == runner_name:
                logging.info("Runner %s status: %s", runner.name, runner.status)
                if runner.status == "online":
                    logging.info(
                        "Runner still marked as online, waiting for it to be marked offline"
                    )
                    sleep(60)
                    break
        else:
            break
    else:
        assert False, "Timeout while waiting for runner to be marked offline"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_runner_installed_metric(app: Application, model: Model):
    """
    arrange: A charm without runners integrated with grafana-agent using the cos-agent integration.
    act: Config the charm to contain one runner.
    assert: The RunnerInstalled metric is logged.
    """

    await ensure_charm_has_runner(app=app, model=model)

    metrics_log = await _get_metrics_log(app.units[0])
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    events = set(map(lambda line: line.get("event"), log_lines))
    assert "runner_installed" in events, "runner_installed event has not been logged"

    for metric_log in log_lines:
        if metric_log.get("event") == "runner_installed":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("event") == "runner_installed"
            assert metric_log.get("duration") >= 0


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_charm_issues_metrics_after_reconciliation(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a workflow on a branch for the runner to run. After completion, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
        The Reconciliation metric has the post job status set to normal.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    await _clear_metrics_log(unit)
    await _dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="success",
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
        app=app, github_repository=forked_github_repository, post_job_status=PostJobStatus.NORMAL
    )


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
    await _clear_metrics_log(unit)
    await _dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="failure",
    )

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
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

    await _wait_for_workflow_to_start(unit, workflow)

    # Make the runner terminate abnormally by killing run.sh
    runner_name = await get_runner_name(unit)
    kill_run_sh_cmd = "pkill -9 run.sh"
    ret_code, _ = await run_in_lxd_instance(unit, runner_name, kill_run_sh_cmd)
    assert ret_code == 0, "Failed to kill run.sh"

    # Cancel workflow and wait that the runner is marked offline
    # to avoid errors during reconciliation.
    await _cancel_workflow_run(unit, workflow)
    await _wait_for_runner_to_be_marked_offline(forked_github_repository, runner_name)

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
        app=app,
        github_repository=forked_github_repository,
        post_job_status=PostJobStatus.ABNORMAL,
    )


async def test_charm_remounts_shared_fs(
    model: Model,
    app: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
):
    """
    arrange: A properly integrated charm with a runner registered on the fork repo.
    act: Dispatch a test workflow and afterwards unmount the shared fs. After that, reconcile.
    assert: The RunnerStart, RunnerStop and Reconciliation metric is logged.
    """
    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    # Clear metrics log to make reconciliation event more predictable
    unit = app.units[0]
    runner_name = await get_runner_name(unit)
    await _clear_metrics_log(unit)
    await _dispatch_workflow(
        app=app,
        branch=forked_github_branch,
        github_repository=forked_github_repository,
        conclusion="success",
    )

    # unmount shared fs
    await run_in_unit(unit, f"sudo umount /home/ubuntu/runner-fs/{runner_name}")

    # Set the number of virtual machines to 0 to speedup reconciliation
    await app.set_config({"virtual-machines": "0"})
    await reconcile(app=app, model=model)

    await _assert_events_after_reconciliation(
        app=app, github_repository=forked_github_repository, post_job_status=PostJobStatus.NORMAL
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
