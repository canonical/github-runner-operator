#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import json
import random
import re
import secrets

import pytest
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from kombu import Connection
from pytest_operator.plugin import OpsTest
from github_runner_manager.reactive.consumer import JobDetails
from github_runner_manager.reactive.runner_manager import REACTIVE_RUNNER_LOG_DIR

from tests.integration.helpers.common import get_file_content, reconcile, run_in_unit

FAKE_URL = "http://example.com"


@pytest.mark.openstack
async def test_reactive_mode_consumes_jobs(ops_test: OpsTest, app_for_reactive: Application):
    """
    arrange: A charm integrated with mongodb and a message is added to the queue.
    act: Call reconcile.
    assert: The message is consumed and the job details are logged.
    """
    unit = app_for_reactive.units[0]
    mongodb_uri = await _get_mongodb_uri_from_integration_data(ops_test, unit)
    if not mongodb_uri:
        mongodb_uri = await _get_mongodb_uri_from_secrets(ops_test, unit.model)
    assert mongodb_uri, "mongodb uri not found in integration data or secret"

    job = JobDetails(
        labels=[secrets.token_hex(16) for _ in range(random.randint(1, 4))], run_url=FAKE_URL
    )
    _add_to_queue(
        json.dumps(job.dict() | {"ignored_noise": "foobar"}),
        mongodb_uri,
        app_for_reactive.name,
    )

    await reconcile(app_for_reactive, app_for_reactive.model)
    _assert_queue_is_empty(mongodb_uri, app_for_reactive.name)
    await _assert_job_details_in_reactive_log(unit, jobs=[job])


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


def _assert_queue_is_empty(mongodb_uri: str, queue_name: str):
    """Assert that the queue is empty.

    Args:
        mongodb_uri: The mongodb uri.
        queue_name: The name of the queue to check.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            assert simple_queue.qsize() == 0


async def _assert_job_details_in_reactive_log(unit: Unit, jobs: list[JobDetails]):
    """Assert that the job details are in the reactive log.

    Args:
        unit: The juju unit.
        jobs: The list of job details to check.
    """
    retcode, stdout, stderr = await run_in_unit(
        unit=unit,
        command=f"ls {REACTIVE_RUNNER_LOG_DIR}",
    )
    assert retcode == 0, f"Failed to list the reactive log dir: {stderr}"
    assert stdout, "No log files found in the reactive log dir."
    log_files = [log_file for log_file in stdout.split()]

    reactive_logs = ""
    for log_file in log_files:
        reactive_logs += await get_file_content(unit, REACTIVE_RUNNER_LOG_DIR / log_file)

    for job in jobs:
        assert job.run_url in reactive_logs
        assert str(job.labels) in reactive_logs
