# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import json
import logging
import socket
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github_runner_manager.reactive.consumer import JobDetails
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import (
    V1JobsJobIdTokenPost200Response,
)
from juju.application import Application
from pytest_httpserver import HTTPServer
from pytest_operator.plugin import OpsTest

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    clear_metrics_log,
)
from tests.integration.helpers.common import reconcile
from tests.integration.helpers.openstack import PrivateEndpointConfigs
from tests.integration.utils_reactive import (
    add_to_queue,
    assert_queue_is_empty,
    clear_queue,
    get_mongodb_uri,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(scope="module", name="image_builder_config")
async def image_builder_config_fixture(
    private_endpoint_config: PrivateEndpointConfigs | None,
    flavor_name: str,
    network_name: str,
):
    """The image builder application default for OpenStack runners."""
    if not private_endpoint_config:
        raise ValueError("Private endpoints are required for testing OpenStack runners.")
    return {
        "build-interval": "12",
        "revision-history-limit": "2",
        "openstack-auth-url": private_endpoint_config["auth_url"],
        # Bandit thinks this is a hardcoded password
        "openstack-password": private_endpoint_config["password"],  # nosec: B105
        "openstack-project-domain-name": private_endpoint_config["project_domain_name"],
        "openstack-project-name": private_endpoint_config["project_name"],
        "openstack-user-domain-name": private_endpoint_config["user_domain_name"],
        "openstack-user-name": private_endpoint_config["username"],
        "build-flavor": flavor_name,
        "build-network": network_name,
        "architecture": "amd64",
        # "script-url": "https://git.launchpad.net/job-manager/plain/scripts/post-image-build.sh?h=main"  # noqa
        "script-url": "https://raw.githubusercontent.com/canonical/github-runner-operator/refs/heads/back-to-first-jobmanager-try/tests/integration/data/post-image-build.sh",  # noqa
    }


@pytest.fixture(scope="session")
def httpserver_listen_port() -> int:
    return 8000


@pytest.fixture(scope="session")
def httpserver_listen_address(httpserver_listen_port: int):
    return ("0.0.0.0", httpserver_listen_port)


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    ops_test: OpsTest,
    app_for_reactive: Application,
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    app_for_jobmanager = app_for_reactive
    mongodb_uri = await get_mongodb_uri(ops_test, app_for_jobmanager)
    clear_queue(mongodb_uri, app_for_jobmanager.name)
    assert_queue_is_empty(mongodb_uri, app_for_jobmanager.name)

    await app_for_jobmanager.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "1",
        }
    )
    await reconcile(app_for_jobmanager, app_for_jobmanager.model)
    await clear_metrics_log(app_for_jobmanager.units[0])

    yield app_for_jobmanager

    # Call reconcile to enable cleanup of any runner spawned
    await app_for_jobmanager.set_config({MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app_for_jobmanager, app_for_jobmanager.model)


@pytest.mark.abort_on_fail
async def test_jobmanager(
    monkeypatch: pytest.MonkeyPatch,
    app: Application,
    ops_test: OpsTest,
    httpserver: HTTPServer,
):
    """
    arrange: Prepare a Job related to the jobmanager.
        Prepare a fake http server to simulate all interactions.
    act: Put the message in the queue.
    assert: Work in progress.
    """
    logger.info("Start of test_jobmanager test")

    # put in a fixture
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use: %s", ip_address)
    s.close()

    port = httpserver.port
    base_url = f"http://{ip_address}:{port}"

    mongodb_uri = await get_mongodb_uri(ops_test, app)
    labels = {app.name, "x64"}

    job_id = 99
    job_path = f"/v1/jobs/{job_id}"
    job_url = f"{base_url}{job_path}"

    job = JobDetails(
        labels=labels,
        url=job_url,
    )

    returned_job = Job(job_id=job_id, status="PENDING")
    httpserver.expect_oneshot_request(job_path).respond_with_json(returned_job.to_dict())

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=10) as waiting:
        add_to_queue(
            json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
            mongodb_uri,
            app.name,
        )
        logger.info("Waiting for first check job status.")
    assert waiting.result

    logger.info("Elapsed time: %s sec", (waiting.elapsed_time))
    logger.info("server log: %s ", (httpserver.log))
    logger.info("matchers: %s ", (httpserver.format_matchers()))

    # ok, now a pending matcher for a while until the runner sends alive
    _ = httpserver.expect_request(job_path).respond_with_json(returned_job.to_dict())

    token_path = f"/v1/jobs/{job_id}/token"
    returned_token = V1JobsJobIdTokenPost200Response(token="token")
    httpserver.expect_oneshot_request(token_path).respond_with_json(returned_token.to_dict())
    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=10) as waiting:
        logger.info("Waiting for get token.")
    assert waiting.result

    logger.info("Elapsed time: %s sec", (waiting.elapsed_time))
    logger.info("server log: %s ", (httpserver.log))
    logger.info("matchers: %s ", (httpserver.format_matchers()))

    assert True, "At this point the builder should be spawned, but pending to replace cloud init."
