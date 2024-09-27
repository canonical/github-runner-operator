#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing reactive mode. This is only supported for the OpenStack cloud."""
import json
import re

import pytest
from github import Branch, Repository
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from kombu import Connection
from pytest_operator.plugin import OpsTest

from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    reconcile,
    wait_for_completion,
)

pytestmark = pytest.mark.openstack


@pytest.fixture(name="setup_queue", autouse=True)
async def setup_queue_fixture(
    ops_test: OpsTest,
    app_for_reactive: Application,
):
    mongodb_uri = await _get_mongodb_uri(ops_test, app_for_reactive)

    _clear_queue(mongodb_uri, app_for_reactive.name)
    _assert_queue_is_empty(mongodb_uri, app_for_reactive.name)


async def test_reactive_mode_spawns_runner(
    ops_test: OpsTest,
    app_for_reactive: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: A charm integrated with mongodb and a message is added to the queue.
    act: Call reconcile.
    assert: The message is consumed and a runner is spawned.
    """
    mongodb_uri = await _get_mongodb_uri(ops_test, app_for_reactive)

    run = await dispatch_workflow(
        app=app_for_reactive,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    jobs = list(run.jobs())
    assert len(jobs) == 1, "Expected 1 job to be created"
    job = jobs[0]
    job_url = job.url
    job = JobDetails(
        labels={app_for_reactive.name, "x64"},  # The architecture label should be ignored in the
        # label validation in the reactive consumer.
        url=job_url,
    )
    _add_to_queue(
        json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
        mongodb_uri,
        app_for_reactive.name,
    )

    await reconcile(app_for_reactive, app_for_reactive.model)

    await wait_for_completion(run, conclusion="success")
    _assert_queue_is_empty(mongodb_uri, app_for_reactive.name)

    # Call reconcile to enable cleanup of the runner
    await reconcile(app_for_reactive, app_for_reactive.model)


async def test_reactive_mode_does_not_consume_jobs_with_unsupported_labels(
    ops_test: OpsTest,
    app_for_reactive: Application,
    github_repository: Repository,
    test_github_branch: Branch,
):
    """
    arrange: A charm integrated with mongodb and an unsupported label is added to the queue.
    act: Call reconcile.
    assert: No runner is spawned and the message is requeued.
    """
    mongodb_uri = await _get_mongodb_uri(ops_test, app_for_reactive)

    run = await dispatch_workflow(
        app=app_for_reactive,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",  # this is ignored currently if wait=False kwarg is used
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        wait=False,
    )
    jobs = list(run.jobs())
    assert len(jobs) == 1, "Expected 1 job to be created"
    job = jobs[0]
    job_url = job.url
    job = JobDetails(labels={"not supported label"}, url=job_url)
    _add_to_queue(
        job.json(),
        mongodb_uri,
        app_for_reactive.name,
    )

    await reconcile(app_for_reactive, app_for_reactive.model)

    run.update()
    assert run.status == "queued"
    run.cancel()

    _assert_queue_has_size(mongodb_uri, app_for_reactive.name, 1)


async def _get_mongodb_uri(ops_test: OpsTest, app_for_reactive: Application) -> str:
    """Get the mongodb uri.

    Args:
        ops_test: The ops_test plugin.
        app_for_reactive: The juju application containing the unit.

    Returns:
        The mongodb uri.

    """
    mongodb_uri = await _get_mongodb_uri_from_integration_data(ops_test, app_for_reactive.units[0])
    if not mongodb_uri:
        mongodb_uri = await _get_mongodb_uri_from_secrets(ops_test, app_for_reactive.model)
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
