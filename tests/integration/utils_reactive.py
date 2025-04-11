#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Utilities for reactive mode."""

import json
import re

from github.WorkflowRun import WorkflowRun
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from kombu import Connection
from pytest_operator.plugin import OpsTest


async def get_mongodb_uri(ops_test: OpsTest, app: Application) -> str:
    """Get the mongodb uri.

    Args:
        ops_test: The ops_test plugin.
        app: The juju application containing the unit.

    Returns:
        The mongodb uri.

    """
    mongodb_uri = await get_mongodb_uri_from_integration_data(ops_test, app.units[0])
    if not mongodb_uri:
        mongodb_uri = await get_mongodb_uri_from_secrets(ops_test, app.model)
    assert mongodb_uri, "mongodb uri not found in integration data or secret"
    return mongodb_uri


async def get_mongodb_uri_from_integration_data(ops_test: OpsTest, unit: Unit) -> str | None:
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


async def get_mongodb_uri_from_secrets(ops_test, model: Model) -> str | None:
    """Get the mongodb uri from the secrets.

    Args:
        ops_test: The ops_test plugin.
        model: The juju model containing the unit.

    Returns:
        The mongodb uri or None if not found.
    """
    mongodb_uri = None

    juju_secrets = await model.list_secrets()

    # Juju < 3.6 returns a dictionary instead of a list
    if not isinstance(juju_secrets, list):
        juju_secrets = juju_secrets["results"]

    for secret in juju_secrets:
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


def create_job_details(run: WorkflowRun, labels: set[str]) -> JobDetails:
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


def add_to_queue(msg: str, mongodb_uri: str, queue_name: str) -> None:
    """Add a message to a queue.

    Args:
        msg: The message to add to the queue.
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to add the message to.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.put(msg, retry=True)


def clear_queue(mongodb_uri: str, queue_name: str) -> None:
    """Clear the queue.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to clear.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.clear()


def assert_queue_is_empty(mongodb_uri: str, queue_name: str):
    """Assert that the queue is empty.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.
    """
    assert_queue_has_size(mongodb_uri, queue_name, 0)


def assert_queue_has_size(mongodb_uri: str, queue_name: str, size: int):
    """Assert that the queue is empty.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.
        size: The expected size of the queue.
    """
    assert get_queue_size(mongodb_uri, queue_name) == size


def get_queue_size(mongodb_uri: str, queue_name: str) -> int:
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
