#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import json
import logging
from typing import AsyncIterator

import jubilant
import pytest
import pytest_asyncio
from github_runner_manager.platform.jobmanager_provider import JobStatus
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from pytest_httpserver import HTTPServer

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
)
from jobmanager.client.jobmanager_client.models.job_read import JobRead
from tests.integration.conftest import DEFAULT_RECONCILE_INTERVAL
from tests.integration.helpers.common import wait_for, wait_for_reconcile
from tests.integration.helpers.openstack import OpenStackInstanceHelper
from tests.integration.jobmanager.helpers import (
    GetRunnerHealthEndpoint,
    add_builder_agent_health_endpoint_response,
    prepare_runner_tunnel_for_builder_agent,
    wait_for_runner_to_be_registered,
)
from tests.integration.utils_reactive import (
    add_to_queue,
    assert_queue_is_empty,
    clear_queue,
    get_mongodb_uri,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(name="app_for_reactive")
async def app_for_reactive_fixture(
    ops_test,
    juju: jubilant.Juju,
    app: Application,
    mongodb: Application,
    jobmanager_base_url: str,
    existing_app_suffix: str,
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    app_for_reactive = app

    if not existing_app_suffix:
        relation = (f"{app_for_reactive.name}:mongodb", f"{mongodb.name}:database")
        juju.integrate(*relation)

    juju.wait(
        lambda status: jubilant.all_active(status, app_for_reactive.name, mongodb.name)
        and jubilant.all_agents_idle(status, app_for_reactive.name, mongodb.name)
    )

    mongodb_uri = await get_mongodb_uri(ops_test, app_for_reactive)
    clear_queue(mongodb_uri, app_for_reactive.name)
    assert_queue_is_empty(mongodb_uri, app_for_reactive.name)

    await app_for_reactive.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            # set larger recon interval as the default due to race condition
            # killing reactive process
            RECONCILE_INTERVAL_CONFIG_NAME: "5",
        }
    )
    await wait_for_reconcile(app_for_reactive)

    yield app_for_reactive

    await app_for_reactive.set_config(
        {
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL),
        }
    )
    await wait_for_reconcile(app_for_reactive)


@pytest.mark.abort_on_fail
async def test_jobmanager_reactive(
    ops_test,
    instance_helper: OpenStackInstanceHelper,
    app_for_reactive: Application,
    httpserver: HTTPServer,
    jobmanager_base_url: str,
    jobmanager_ip_address: str,
):
    """
    Test reactive mode together with jobmanager.

    Test that after putting a job in the queue that the runner is registered and the
    job is picked up.

    So,
    1. Put job in the queue
    2. Wait for runner to be registered
    3. Wait for reactive process to ask for job status
    4. Mark job deletable
    5. Reconcile
    6. Assert queue is empty
    """
    runner_id = 1234
    runner_token = "token"
    runner_health_path = f"/v1/runners/{runner_id}/health"

    # The builder-agent can get to us at any point.
    add_builder_agent_health_endpoint_response(
        app_for_reactive, httpserver, runner_health_path, runner_token, status="IDLE"
    )
    add_builder_agent_health_endpoint_response(
        app_for_reactive, httpserver, runner_health_path, runner_token, status="EXECUTING"
    )
    add_builder_agent_health_endpoint_response(
        app_for_reactive, httpserver, runner_health_path, runner_token, status="FINISHED"
    )

    # 1. Put job in the queue
    mongodb_uri = await get_mongodb_uri(ops_test, app_for_reactive)
    labels = {app_for_reactive.name, "x64"}

    job_id = 99
    job_path = f"/v1/jobs/{job_id}"
    job_url = f"{jobmanager_base_url}{job_path}"

    job = JobDetails(
        labels=labels,
        url=job_url,
    )

    # The first interaction with the jobmanager after the runner manager gets
    # a message in the queue is to check if the job has been picked up. If it is pending,
    # the github-runner will spawn a reactive runner.
    returned_job = JobRead(
        id=job_id,
        status=JobStatus.PENDING.value,
        architecture="x64",
        base_series="jammy",
        requested_by="foobar",
    )
    httpserver.expect_oneshot_request(job_path).respond_with_json(returned_job.to_dict())

    with httpserver.wait(
        raise_assertions=True, stop_on_nohandler=False, timeout=60 * 2
    ) as waiting:
        add_to_queue(
            json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
            mongodb_uri,
            app_for_reactive.name,
        )
        logger.info("Waiting for first check job status.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed Waiting for first check job status."

    # From this point, the github-runner reactive process will check if the job has been picked
    # up. The jobmanager will return pending until the builder-agent is alive (that is,
    # the server is alive and running).
    job_get_handler = httpserver.expect_request(job_path)
    job_get_handler.respond_with_json(returned_job.to_dict())

    # 2. Wait for runner to be registered
    await wait_for_runner_to_be_registered(httpserver, runner_id, runner_token)

    # For the github runner manager, at this point, the jobmanager will return
    # that the runner health is pending and not deletable
    runner_health_endpoint = GetRunnerHealthEndpoint(httpserver, runner_health_path)
    runner_health_endpoint.set(status="PENDING", deletable=False)

    unit = app_for_reactive.units[0]

    async def _prepare_runner() -> bool:
        """Prepare the tunner so the runner builder-agent can get to the jobmanager."""
        return await prepare_runner_tunnel_for_builder_agent(
            instance_helper, unit, jobmanager_ip_address, httpserver.port
        )

    await wait_for(_prepare_runner, check_interval=10, timeout=600)

    # 3. Wait for reactive process to ask for job status
    runner_health_endpoint.set(status="IN_PROGRESS", deletable=False)

    returned_job.status = JobStatus.IN_PROGRESS.value
    job_get_handler = httpserver.expect_oneshot_request(job_path)
    job_get_handler.respond_with_json(returned_job.to_dict())

    with httpserver.wait(raise_assertions=True, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for job status to be queried.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed waiting for job status to be queried."

    # 4. Mark runner deletable
    runner_health_endpoint.set(status="COMPLETED", deletable=True)

    # 5. Reconcile
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app_for_reactive.set_config(
        {RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL + 1)}
    )
    await wait_for_reconcile(app_for_reactive)

    # 6. Assert queue is empty
    assert_queue_is_empty(mongodb_uri, app_for_reactive.name)
