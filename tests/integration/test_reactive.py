#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing reactive mode. This is only supported for the OpenStack cloud."""
import json
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github import Branch, Repository
from github_runner_manager.manager.cloud_runner_manager import PostJobStatus
from juju.application import Application
from pytest_operator.plugin import OpsTest

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    assert_events_after_reconciliation,
    clear_metrics_log,
    get_metrics_log,
)
from tests.integration.helpers.common import (
    DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    reconcile,
    wait_for,
    wait_for_completion,
    wait_for_status,
)
from tests.integration.utils_reactive import (
    add_to_queue,
    assert_queue_has_size,
    assert_queue_is_empty,
    clear_queue,
    create_job_details,
    get_mongodb_uri,
    get_queue_size,
)

pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    ops_test: OpsTest, app_for_reactive: Application
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    mongodb_uri = await get_mongodb_uri(ops_test, app_for_reactive)
    clear_queue(mongodb_uri, app_for_reactive.name)
    assert_queue_is_empty(mongodb_uri, app_for_reactive.name)

    await app_for_reactive.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "1",
        }
    )
    await reconcile(app_for_reactive, app_for_reactive.model)
    await clear_metrics_log(app_for_reactive.units[0])

    yield app_for_reactive

    # Call reconcile to enable cleanup of any runner spawned
    await app_for_reactive.set_config({MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app_for_reactive, app_for_reactive.model)


@pytest.mark.abort_on_fail
async def test_reactive_mode_spawns_runner(
    ops_test: OpsTest,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: Place a message in the queue and dispatch a workflow.
    act: Call reconcile.
    assert: A runner is spawned to process the job and the message is removed from the queue.
        The metrics are logged.
    """
    mongodb_uri = await get_mongodb_uri(ops_test, app)

    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    labels = {app.name, "x64"}  # The architecture label should be ignored in the
    # label validation in the reactive consumer.
    job = create_job_details(run=run, labels=labels)
    add_to_queue(
        json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
        mongodb_uri,
        app.name,
    )

    # This reconcile call is to check that we are not killing machines that are under
    # construction in a subsequent reconciliation.
    await reconcile(app, app.model)

    try:
        await wait_for_completion(run, conclusion="success")
    except TimeoutError:
        assert False, (
            "Job did not complete successfully, check the reactive log using tmate,"
            " it might be due to infrastructure issues"
        )

    assert_queue_is_empty(mongodb_uri, app.name)

    async def _runner_installed_in_metrics_log() -> bool:
        """Check if the runner_installed event is logged in the metrics log.

        Returns:
            True if the runner_installed event is logged, False otherwise.
        """
        # trigger reconcile which extracts metrics
        await reconcile(app, app.model)
        metrics_log = await get_metrics_log(app.units[0])
        log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
        events = set(map(lambda line: line.get("event"), log_lines))
        return "runner_installed" in events

    try:
        await wait_for(_runner_installed_in_metrics_log, check_interval=30, timeout=60 * 10)
    except TimeoutError:
        assert False, "runner_installed event has not been logged"

    await _assert_metrics_are_logged(app, github_repository)


@pytest.mark.abort_on_fail
async def test_reactive_mode_does_not_consume_jobs_with_unsupported_labels(
    ops_test: OpsTest,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: Place a message with an unsupported label in the queue and dispatch a workflow.
    act: Call reconcile.
    assert: No runner is spawned and the message is not requeued.
    """
    mongodb_uri = await get_mongodb_uri(ops_test, app)
    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = create_job_details(run=run, labels={"not supported label"})
    add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    # wait for queue being empty, there could be a race condition where it takes some
    # time for the job message to be consumed and the queue to be empty
    try:
        await wait_for(lambda: get_queue_size(mongodb_uri, app.name) == 0)
        run.update()
        assert run.status == "queued"
    finally:
        run.cancel()  # cancel the run to avoid a queued run in GitHub actions page


@pytest.mark.abort_on_fail
async def test_reactive_mode_scale_down(
    ops_test: OpsTest,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: Scale down the number of virtual machines to 2 and spawn a job.
    act:
        1. Scale down the number of virtual machines to 0 and call reconcile.
        2. Spawn a job.
    assert:
        1. The job fails.
        2. The job is queued and there is a message in the queue.
    """
    mongodb_uri = await get_mongodb_uri(ops_test, app)

    await app.set_config({MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "2"})
    await reconcile(app, app.model)

    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = create_job_details(run=run, labels={app.name})
    add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    await wait_for_status(run, "in_progress")

    # 1. Scale down the number of virtual machines to 0 and call reconcile.
    await app.set_config({MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app, app.model)

    # we assume that the runner got deleted while running the job, so we expect a failed job
    await wait_for_completion(run, conclusion="failure")
    assert_queue_is_empty(mongodb_uri, app.name)

    # 2. Spawn a job.
    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = create_job_details(run=run, labels={app.name})
    add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    await reconcile(app, app.model)

    run.update()
    assert run.status == "queued"
    run.cancel()

    assert_queue_has_size(mongodb_uri, app.name, 1)


async def _assert_metrics_are_logged(app: Application, github_repository: Repository):
    """Assert that all runner metrics are logged.

    Args:
        app: The juju application, used to extract the metrics log and flavor name.
        github_repository: The GitHub repository to be included in the metrics.
    """
    metrics_log = await get_metrics_log(app.units[0])
    log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
    for metric_log in log_lines:
        if metric_log.get("event") == "runner_installed":
            assert metric_log.get("flavor") == app.name
            assert metric_log.get("event") == "runner_installed"
            assert metric_log.get("duration") >= 0
    await assert_events_after_reconciliation(
        app=app,
        github_repository=github_repository,
        post_job_status=PostJobStatus.NORMAL,
        reactive_mode=True,
    )
