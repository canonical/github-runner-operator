# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import http.server
import json
import logging
import socket
import socketserver
from typing import AsyncIterator, Optional

import pytest
import pytest_asyncio
from github_runner_manager.reactive.consumer import JobDetails
from jobmanager_client.models.job import Job
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    clear_metrics_log,
)
from tests.integration.helpers.common import reconcile
from tests.integration.utils_reactive import (
    add_to_queue,
    assert_queue_is_empty,
    clear_queue,
    get_mongodb_uri,
)

logger = logging.getLogger(__name__)

# TODO copy pasted from test_reactive and other places. Refactor in a common place
# Very inefficient


@pytest_asyncio.fixture(scope="module", name="app_for_jobmanager")
async def app_for_jobmanager_fixture(
    model: Model,
    app_openstack_runner: Application,
    mongodb: Application,
    existing_app_suffix: Optional[str],
    image_builder: Application,
) -> Application:
    """Application for testing reactive jobmanager."""
    await image_builder.set_config(
        {
            "script-url": "https://git.launchpad.net/job-manager/plain/scripts/post-image-build.sh?h=main"
        }
    )

    logger.info("app_for_jobmanager fixture")
    if not existing_app_suffix:
        await model.relate(f"{app_openstack_runner.name}:mongodb", f"{mongodb.name}:database")

    await model.wait_for_idle(
        apps=[app_openstack_runner.name, image_builder.name, mongodb.name],
        status=ActiveStatus.name,
    )
    logger.info("app_for_jobmanager fixture ready")

    return app_openstack_runner


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    ops_test: OpsTest, app_for_jobmanager: Application
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
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
):
    """
    arrange: TODO.
    act: TODO.
    assert: TODO.
    """
    logger.info("Start of test_jobmanager test")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use: %s", ip_address)
    s.close()

    port = 8000
    base_url = f"http://{ip_address}:{port}/"

    mongodb_uri = await get_mongodb_uri(ops_test, app)
    labels = {app.name, "x64"}

    job_id = 99
    job_url = f"{base_url}/v1/jobs/{job_id}"

    job = JobDetails(
        labels=labels,
        url=job_url,
    )

    with TestServer(monkeypatch, ("", 8000)) as httpd:
        add_to_queue(
            json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
            mongodb_uri,
            app.name,
        )

        returned_job = Job()
        httpd.handle_get_request(
            f"/v1/jobs/{job_id}", json.dumps(returned_job.to_json()), timeout=5
        )

        # here the agent will v1/jobs/{job_id}/health

        # here github-runner go also v1/jobs/{job_id}

        # ...
        # here I call the agent in 8080 to execute "ls"

        # agent will listen in 8080 for jobs to execute.
        # we need another security special group for jobmanager.
    assert True


class TestHandler(http.server.BaseHTTPRequestHandler):
    """TODO."""

    def do_GET(self):  # noqa: N802
        """TODO."""
        self.send_error(404)


class TestServer(socketserver.TCPServer):
    """TODO."""  # noqa: DCO020, DCO060

    allow_reuse_address = True

    def __init__(self, monkeypatch, server_address, bind_and_activate=True):
        """TODO."""  # noqa: DCO020, DCO060
        # Using monkeypatch for now as it is easy
        self.monkeypatch = monkeypatch
        # So we do not want other server handler.
        self.mock_handler = type("", (TestHandler,), {})
        super().__init__(server_address, self.mock_handler, bind_and_activate)

    def handle_get_request(self, url, response, timeout=10):
        """TODO."""  # noqa: DCO020, DCO060, DCO050
        self.timeout = timeout
        handler_executed = False

        def _handler(handler):
            """TODO."""
            nonlocal handler_executed
            # TODO FAIL IR URL IS WRONG!
            handler.send_response(200, "OK")
            handler.end_headers()
            handler.wfile.write(response.encode("utf-8"))
            handler_executed = True

        try:
            oldval = getattr(self.mock_handler, "do_GET")
            setattr(self.mock_handler, "do_GET", _handler)
            self.handle_request()
            if not handler_executed:
                raise AssertionError("GRR, not called.")
        finally:
            setattr(self.mock_handler, "do_GET", oldval)
