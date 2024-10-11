#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing reactive mode. This is only supported for the OpenStack cloud."""
import json
import re
from time import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github import Branch, Repository
from github.WorkflowRun import WorkflowRun
from github_runner_manager.metrics.runner import PostJobStatus
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from kombu import Connection
from pytest_operator.plugin import OpsTest

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    assert_events_after_reconciliation,
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

pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    ops_test: OpsTest, app_for_reactive: Application
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    mongodb_uri = await _get_mongodb_uri(ops_test, app_for_reactive)
    _clear_queue(mongodb_uri, app_for_reactive.name)
    _assert_queue_is_empty(mongodb_uri, app_for_reactive.name)

    await app_for_reactive.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await reconcile(app_for_reactive, app_for_reactive.model)

    yield app_for_reactive

    # Call reconcile to enable cleanup of any runner spawned
    await app_for_reactive.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app_for_reactive, app_for_reactive.model)


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
    mongodb_uri = await _get_mongodb_uri(ops_test, app)

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
    job = _create_job_details(run=run, labels=labels)
    _add_to_queue(
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

    _assert_queue_is_empty(mongodb_uri, app.name)

    async def _runner_installed_in_metrics_log():
        # trigger reconcile which extracts metrics
        await reconcile(app, app.model)
        metrics_log = await get_metrics_log(app.units[0])
        log_lines = list(map(lambda line: json.loads(line), metrics_log.splitlines()))
        events = set(map(lambda line: line.get("event"), log_lines))
        return "runner_installed" in events

    try:
        await wait_for(_runner_installed_in_metrics_log, check_interval=30)
    except TimeoutError:
        assert False, "runner_installed event has not been logged"

    await _assert_metrics_are_logged(app, github_repository)



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
    mongodb_uri = await _get_mongodb_uri(ops_test, app)
    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = _create_job_details(run=run, labels={"not supported label"})
    _add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    # wait for queue being empty, there could be a race condition where it takes some
    # time for the job message to be consumed and the queue to be empty
    try:
        await wait_for(lambda: _get_queue_size(mongodb_uri, app.name) == 0)
        run.update()
        assert run.status == "queued"
    finally:
        run.cancel()  # cancel the run to avoid a queued run in GitHub actions page


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
    mongodb_uri = await _get_mongodb_uri(ops_test, app)

    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "2"})
    await reconcile(app, app.model)

    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = _create_job_details(run=run, labels={app.name})
    _add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    await wait_for_status(run, "in_progress")

    # 1. Scale down the number of virtual machines to 0 and call reconcile.
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app, app.model)

    # we assume that the runner got deleted while running the job, so we expect a failed job
    await wait_for_completion(run, conclusion="failure")
    _assert_queue_is_empty(mongodb_uri, app.name)

    # 2. Spawn a job.
    run = await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    job = _create_job_details(run=run, labels={app.name})
    _add_to_queue(
        job.json(),
        mongodb_uri,
        app.name,
    )

    await reconcile(app, app.model)

    run.update()
    assert run.status == "queued"
    run.cancel()

    _assert_queue_has_size(mongodb_uri, app.name, 1)


async def _get_mongodb_uri(ops_test: OpsTest, app: Application) -> str:
    """Get the mongodb uri.

    Args:
        ops_test: The ops_test plugin.
        app: The juju application containing the unit.

    Returns:
        The mongodb uri.

    """
    mongodb_uri = await _get_mongodb_uri_from_integration_data(ops_test, app.units[0])
    if not mongodb_uri:
        mongodb_uri = await _get_mongodb_uri_from_secrets(ops_test, app.model)
    assert mongodb_uri, "mongodb uri not found in integration data or secret"
    return mongodb_uri


async def _get_mongodb_uri_from_integration_data(ops_test: OpsTest, unit: Unit) -> str | None:
    """Get the mongodb uri from the relation data.

    Args:
        ops_test: The ops_test plugin.
        unit: The juju unit containing the relation data.

    Returns:
        The mongodb uri or None if not found.
    """
    mongodb_uri = None
    _, unit_data, _ = await ops_test.juju("show-unit", unit.name, "--format", "json")
    unit_data = json.loads(unit_data)

    for rel_info in unit_data[unit.name]["relation-info"]:
        if rel_info["endpoint"] == "mongodb":
            try:
                mongodb_uri = rel_info["application-data"]["uris"]
                break
            except KeyError:
                pass

    return mongodb_uri


async def _get_mongodb_uri_from_secrets(ops_test, model: Model) -> str | None:
    """Get the mongodb uri from the secrets.

    Args:
        ops_test: The ops_test plugin.
        model: The juju model containing the unit.

    Returns:
        The mongodb uri or None if not found.
    """
    mongodb_uri = None

    juju_secrets = await model.list_secrets()
    for secret in juju_secrets["results"]:
        if re.match(r"^database.\d+.user.secret$", secret.label):
            _, show_secret, _ = await ops_test.juju(
                "show-secret", secret.uri, "--reveal", "--format", "json"
            )
            show_secret = json.loads(show_secret)
            for value in show_secret.values():
                if "content" in value:
                    mongodb_uri = value["content"]["Data"]["uris"]
                    break
            if mongodb_uri:
                break
    return mongodb_uri


def _create_job_details(run: WorkflowRun, labels: set[str]) -> JobDetails:
    """Create a JobDetails object.

    Args:
        run: The workflow run containing the job. Used to retrieve the job url. We assyne
            the run only contains one job.
        labels: The labels for the job.

    Returns:
        The job details.
    """
    jobs = list(run.jobs())
    assert len(jobs) == 1, "Expected 1 job to be created"
    job = jobs[0]
    job_url = job.url
    job = JobDetails(
        labels=labels,
        url=job_url,
    )
    return job


def _add_to_queue(msg: str, mongodb_uri: str, queue_name: str) -> None:
    """Add a message to a queue.

    Args:
        msg: The message to add to the queue.
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to add the message to.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.put(msg, retry=True)


def _clear_queue(mongodb_uri: str, queue_name: str) -> None:
    """Clear the queue.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to clear.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.clear()


def _assert_queue_is_empty(mongodb_uri: str, queue_name: str):
    """Assert that the queue is empty.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.
    """
    _assert_queue_has_size(mongodb_uri, queue_name, 0)


def _assert_queue_has_size(mongodb_uri: str, queue_name: str, size: int):
    """Assert that the queue is empty.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.
        size: The expected size of the queue.
    """
    assert _get_queue_size(mongodb_uri, queue_name) == size


def _get_queue_size(mongodb_uri: str, queue_name: str) -> int:
    """Get the size of the queue.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.

    Returns:
        The size of the queue.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            return simple_queue.qsize()


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
    )
