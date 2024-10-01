#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing reactive mode. This is only supported for the OpenStack cloud."""
import json
import re
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github import Branch, Repository
from github.WorkflowRun import WorkflowRun
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from kombu import Connection
from pytest_operator.plugin import OpsTest

from charm_state import VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    reconcile,
    wait_for_completion,
    wait_for_status,
)

pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(name="app")
async def app_fixture(app_for_reactive: Application) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine."""
    await app_for_reactive.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await reconcile(app_for_reactive, app_for_reactive.model)

    yield app_for_reactive

    # Call reconcile to enable cleanup of any runner spawned
    await reconcile(app_for_reactive, app_for_reactive.model)


@pytest_asyncio.fixture(name="setup_queue", autouse=True)
async def setup_queue_fixture(
    ops_test: OpsTest,
    app: Application,
):
    mongodb_uri = await _get_mongodb_uri(ops_test, app)

    _clear_queue(mongodb_uri, app.name)
    _assert_queue_is_empty(mongodb_uri, app.name)


async def test_reactive_mode_spawns_runner(
    ops_test: OpsTest,
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: Place a message in the queue and dispatch a workflow.
    act: Call reconcile.
    assert: A  runner is spawned to process the job and the message is removed from the queue.
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

    await reconcile(app, app.model)

    await wait_for_completion(run, conclusion="success")

    # there is an edge case that reconciliation kills a process that has not yet
    # acknowledged the message, so we trigger again a reconciliation and assume that
    # the next process will pick up the message if it was not acknowledged
    await reconcile(app, app.model)

    _assert_queue_is_empty(mongodb_uri, app.name)


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

    await reconcile(app, app.model)

    run.update()
    assert run.status == "queued"

    try:
        _assert_queue_is_empty(mongodb_uri, app.name)
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
    # there is an edge case that reconciliation kills a process that has not yet
    # acknowledged the message, so we clear the queue
    _clear_queue(mongodb_uri, app.name)

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
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            assert simple_queue.qsize() == size
