#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Utilities for charm metrics integration tests."""


import datetime
import json
import logging
from time import sleep

import requests
from github.Branch import Branch
from github.GithubException import GithubException
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowJob import WorkflowJob
from juju.application import Application
from juju.unit import Unit

from github_type import JobConclusion
from metrics.events import METRICS_LOG_PATH
from metrics.runner import PostJobStatus
from tests.integration.helpers import get_runner_name, run_in_unit, wait_for

logger = logging.getLogger(__name__)

TEST_WORKFLOW_NAMES = [
    "Workflow Dispatch Tests",
    "Workflow Dispatch Crash Tests",
    "Workflow Dispatch Failure Tests 2a34f8b1-41e4-4bcb-9bbf-7a74e6c482f7",
]


async def wait_for_workflow_to_start(
    unit: Unit,
    workflow: Workflow,
    branch: Branch | None = None,
    started_time: float | None = None,
    timeout: int = 20 * 60,
):
    """Wait for the workflow to start.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to wait for.
        branch: The branch where the workflow belongs to.
        started_time: The time in seconds since epoch the job was started.
        timeout: Timeout in seconds to wait for the workflow to start.

    Raises:
        TimeoutError: If the workflow didn't start for specified time period.
    """
    runner_name = await get_runner_name(unit)
    created_at = (
        None
        if not started_time
        # convert to integer since GH API takes up to seconds.
        else f">={datetime.datetime.fromtimestamp(int(started_time)).isoformat()}"
    )

    def is_runner_log():
        """Return whether a log for given runner exists.

        Returns:
            Whether the log exists.
        """
        for run in workflow.get_runs(branch=branch, created=created_at):
            jobs = run.jobs()
            if not jobs:
                return False
            try:
                job: WorkflowJob = jobs[0]
                logs = requests.get(job.logs_url()).content.decode("utf-8")
            except GithubException as exc:
                if exc.status == 410:
                    logger.warning("Transient github error, %s", exc)
                    return False
            if runner_name in logs:
                return True
        return False

    try:
        await wait_for(is_runner_log, timeout=timeout, check_interval=30)
    except TimeoutError as exc:
        raise TimeoutError("Timeout while waiting for the workflow to start") from exc


async def clear_metrics_log(unit: Unit) -> None:
    """Clear the metrics log on the unit.

    Args:
        unit: The unit to clear the metrics log on.
    """
    retcode, _, stderr = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then rm {METRICS_LOG_PATH}; fi",
    )
    assert retcode == 0, f"Failed to clear metrics log, {stderr}"


async def print_loop_device_info(unit: Unit, loop_device: str) -> None:
    """Print loop device info on the unit.

    Args:
        unit: The unit to print the loop device info on.
        loop_device: The loop device to print the info for.
    """
    retcode, stdout, stderr = await run_in_unit(
        unit=unit,
        command="sudo losetup -lJ",
    )
    assert retcode == 0, f"Failed to get loop devices: {stdout} {stderr}"
    assert stdout is not None, "Failed to get loop devices, no stdout message"
    loop_devices_info = json.loads(stdout)
    for loop_device_info in loop_devices_info["loopdevices"]:
        if loop_device_info["name"] == loop_device:
            logging.info("Loop device %s info: %s", loop_device, loop_device_info)
            break
    else:
        logging.info("Loop device %s not found", loop_device)


async def get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    retcode, stdout, stderr = await run_in_unit(
        unit=unit,
        command=f"if [ -f {METRICS_LOG_PATH} ]; then cat {METRICS_LOG_PATH}; else echo ''; fi",
    )
    assert retcode == 0, f"Failed to get metrics log: {stdout} {stderr}"
    assert stdout is not None, "Failed to get metrics log, no stdout message"
    logging.info("Metrics log: %s", stdout)
    return stdout.strip()


async def cancel_workflow_run(unit: Unit, workflow: Workflow, branch: Branch | None = None):
    """Cancel the workflow run.

    Args:
        unit: The unit which contains the runner.
        workflow: The workflow to cancel the workflow run for.
        branch: The branch where the workflow belongs to.
    """
    runner_name = await get_runner_name(unit)

    for run in workflow.get_runs(branch=branch):
        jobs = run.jobs()
        if not jobs:
            continue
        try:
            job: WorkflowJob = jobs[0]
            logs = requests.get(job.logs_url()).content.decode("utf-8")
        except GithubException as exc:
            if exc.status == 410:
                logger.warning("Transient github error, %s", exc)
                continue
        if runner_name in logs:
            run.cancel()


async def assert_events_after_reconciliation(
    app: Application, github_repository: Repository, post_job_status: PostJobStatus
):
    """Assert that the RunnerStart, RunnerStop and Reconciliation metric is logged.

    Args:
        app: The charm to assert the events for.
        github_repository: The github repository to assert the events for.
        post_job_status: The expected post job status of the reconciliation event.
    """
    unit = app.units[0]

    metrics_log = await get_metrics_log(unit=unit)
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


async def wait_for_runner_to_be_marked_offline(
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
