# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import asyncio
import json
import logging
import socket
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github_runner_manager.platform.jobmanager_provider import JobStatus
from github_runner_manager.reactive.consumer import JobDetails
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_health_get200_response import (
    V1JobsJobIdHealthGet200Response,
)
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import (
    V1JobsJobIdTokenPost200Response,
)
from juju.application import Application
from pytest_httpserver import HTTPServer
from pytest_operator.plugin import OpsTest

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import clear_metrics_log
from tests.integration.helpers.common import reconcile, wait_for
from tests.integration.helpers.openstack import OpenStackInstanceHelper, PrivateEndpointConfigs
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
        "script-url": "https://git.launchpad.net/job-manager/plain/scripts/post-image-build.sh?h=main",  # noqa
    }


@pytest.fixture(scope="session")
def httpserver_listen_port() -> int:
    # Do not use the listening port of the builder-agent, as it
    # will interfere with the tunnel from the runner to the
    # mock jobmanager.
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
    instance_helper: OpenStackInstanceHelper,
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
    # The http server simulates the jobmanager. Both the github-runner application
    # and the builder-agent will interact with the jobmanager. An alternative is
    # to create a test with a real jobmanager, and this could be done in the future.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use as the fake jobmanager: %s", ip_address)
    s.close()

    jobmanager_base_url = f"http://{ip_address}:{httpserver.port}"

    mongodb_uri = await get_mongodb_uri(ops_test, app)
    labels = {app.name, "x64"}

    job_id = 99
    job_path = f"/v1/jobs/{job_id}"
    job_path_health = f"/v1/jobs/{job_id}/health"
    job_url = f"{jobmanager_base_url}{job_path}"

    job = JobDetails(
        labels=labels,
        url=job_url,
    )

    # The first interaction with the jobmanager after the runner manager gets
    # a message in the queue is to check if the job has been picked up. If it is pending,
    # the github-runner will spawn a reactive runner.
    returned_job = Job(job_id=job_id, status=JobStatus.PENDING.value)

    httpserver.expect_oneshot_request(job_path).respond_with_json(returned_job.to_dict())

    with httpserver.wait(
        raise_assertions=False, stop_on_nohandler=False, timeout=60 * 2
    ) as waiting:
        add_to_queue(
            json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
            mongodb_uri,
            app.name,
        )
        logger.info("Waiting for first check job status.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed Waiting for first check job status."

    # From this point, the github-runner reactive process will check if the job has been picked
    # up. The jobmanager will return pending until the builder-agent is alive (that is,
    # the server is alive and running).
    httpserver.expect_request(job_path).respond_with_json(returned_job.to_dict())

    # The runner manager will request a token to spawn the runner.
    token_path = f"/v1/jobs/{job_id}/token"
    returned_token = V1JobsJobIdTokenPost200Response(token="token")
    httpserver.expect_oneshot_request(token_path).respond_with_json(returned_token.to_dict())

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for get token.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed Waiting for get token."

    # The builder-agent can get to us at any point.
    # the builder-agent will make PUT requests to
    # http://{ip_address}:{httpserver.port}/v1/jobs/{job_id}/health.
    # It will send a jeon like {"label": "label", "status": "IDLE"}
    # status can be: IDLE, EXECUTING, FINISHED,
    # It should have an Authorization header like: ("Authorization", "Bearer "+BEARER_TOKEN)
    base_builder_agent_health_request = {
        "uri": job_path_health,
        "method": "PUT",
        "headers": {"Authorization": "Bearer token"},
    }
    json_idle = {"json": {"label": app.name, "status": "IDLE"}}
    json_executing = {"json": {"label": app.name, "status": "EXECUTING"}}
    json_finished = {"json": {"label": app.name, "status": "FINISHED"}}

    httpserver.expect_request(**base_builder_agent_health_request | json_idle).respond_with_data(
        "OK"
    )

    # At this point the openstack instance will be spawned.

    # For the github runner manager, at this point, the jobmanager will return
    # that the job health is pending and not deletable
    # '/v1/jobs/{job_id}/health', 'GET',
    # Returns V1JobsJobIdHealthGet200Response
    health_response = V1JobsJobIdHealthGet200Response(
        label="label",
        cpu_usage="1",
        ram_usage="1",
        disk_usage="1",
        status="PENDING",
        deletable=False,
    )
    httpserver.expect_request(uri=job_path_health, method="GET").respond_with_json(
        health_response.to_dict()
    )

    unit = app.units[0]

    async def _prepare_runner() -> bool:
        """Prepare the tunner so the runner builder-agent can get to the jobmanager."""
        return await _prepare_runner_tunnel_for_builder_agent(
            instance_helper, unit, ip_address, httpserver.port
        )

    await wait_for(_prepare_runner, check_interval=10, timeout=600)

    # We want to hear from the builder-agent the runs in the instance at least once.
    httpserver.expect_oneshot_request(
        **base_builder_agent_health_request | json_idle
    ).respond_with_data("OK")
    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for builder-agent to contact us.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "builder-agent did not contact us."

    # ok, at this point reply from the jobmanager that the runner is in progress.
    health_response = V1JobsJobIdHealthGet200Response(
        label="label",
        cpu_usage="1",
        ram_usage="1",
        disk_usage="1",
        status="IN_PROGRESS",
        deletable=False,
    )
    httpserver.expect_request(uri=job_path_health, method="GET").respond_with_json(
        health_response.to_dict()
    )

    httpserver.check_assertions()

    # Ok, at this point, we want to tell the builder-agent to execute some command,
    # specifically a sleep so we can check that it goes over executing and finished statuses.
    await _execute_command_with_builder_agent(instance_helper, unit, "sleep 30")

    httpserver.expect_oneshot_request(
        **base_builder_agent_health_request | json_executing
    ).respond_with_data("OK")
    httpserver.expect_request(
        **base_builder_agent_health_request | json_executing
    ).respond_with_data("OK")
    httpserver.expect_oneshot_request(
        **base_builder_agent_health_request | json_finished
    ).respond_with_data("OK")
    httpserver.expect_request(
        **base_builder_agent_health_request | json_finished
    ).respond_with_data("OK")

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=120) as waiting:
        logger.info("Waiting for builder-agent to contact us.")
    logger.info("server log after executing: %s ", (httpserver.log))
    assert waiting.result, "builder-agent did not execute or finished."

    httpserver.check_assertions()

    assert_queue_is_empty(mongodb_uri, app.name)

    # The reconcile loop is still not adapted and will badly kill the instance as the ssh
    # health check will mark the instance as unhealthy.


async def _prepare_runner_tunnel_for_builder_agent(
    instance_helper, unit, jobmanager_address, jobmanager_port
) -> bool:
    """Prepare the runner tunner so the builder-agent can access the fake jobmanager.

    This function will change the address of the traffic going to the jobmanager_address
    and jobmanager_port to the jobmanager_port in the address 127.0.0.1 inside the runner.
    A reverse tunnel will be then created that will listen in the runner in the
    address 127.0.0.1 and the port jobmanager_port and will send the traffic to the
    fake jobmanager http server. This is required as the runner may be unable to send traffic
    directly to the fake http server running in this test.

    This function return False if the tunnel could not be prepared and
    retrying is possible.
    """
    logger.info("trying to prepare tunnel for builder agent")
    try:
        server = instance_helper.get_single_runner(unit)
    except AssertionError:
        logger.info("no runner or two or more runners in unit, return False")
        return False
    network_address_list = server.addresses.values()
    if not network_address_list:
        logger.info("no addresses yet, return False")
        return False

    exit_code, stdout, _ = await instance_helper.run_in_instance(
        unit,
        "'echo hello'",
        timeout=10,
    )
    if exit_code != 0 or not stdout or "hello" not in stdout:
        logger.info("cannot ssh yet, return False")
        return False

    # Not sure about this. We should check if the nftables interfere with the iptables rules.
    # For now, a sleep for a bit of time so we the runner has time to flush and apply the
    # nftables rules. We may also check this issue in other tests.
    await asyncio.sleep(60)

    dnat_comman_in_runner = f"sudo iptables -t nat -A OUTPUT -p tcp -d {jobmanager_address} --dport {jobmanager_port} -j DNAT --to-destination 127.0.0.1:{jobmanager_port}"  # noqa  # pylint: disable=line-too-long
    exit_code, _, _ = await instance_helper.run_in_instance(
        unit,
        dnat_comman_in_runner,
        timeout=10,
    )
    assert exit_code == 0, "could not apply iptables"
    await instance_helper.expose_to_instance(
        unit=unit, port=jobmanager_port, host=jobmanager_address
    )
    return True


async def _execute_command_with_builder_agent(instance_helper, unit, command) -> None:
    """Execute a command in the builder-agent."""
    execute_command = (
        "'curl http://127.0.0.1:8080/execute -X POST "
        '--header "Content-Type: application/json" '
        '--data "'
        f'{{\\"commands\\":[\\"{command}\\"]}}"'
        "'"
    )
    _, _, _ = await instance_helper.run_in_instance(
        unit=unit,
        command=execute_command,
        assert_on_failure=True,
        timeout=10,
        assert_msg="Failed executing commands in builder-agent",
    )
