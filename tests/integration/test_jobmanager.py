# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import asyncio
import json
import logging
import socket
from typing import AsyncIterator

import jubilant
import pytest
import pytest_asyncio
from github_runner_manager.platform.jobmanager_provider import JobStatus
from github_runner_manager.reactive.consumer import JobDetails
from juju.application import Application
from pytest_httpserver import HTTPServer, RequestHandler

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
)
from jobmanager.client.jobmanager_client.models.get_runner_health_v1_runner_runner_id_health_get200_response import (
    GetRunnerHealthV1RunnerRunnerIdHealthGet200Response,
)
from jobmanager.client.jobmanager_client.models.job_read import JobRead
from jobmanager.client.jobmanager_client.models.register_runner_v1_runner_register_post200_response import (
    RegisterRunnerV1RunnerRegisterPost200Response,
)
from tests.integration.conftest import DEFAULT_RECONCILE_INTERVAL
from tests.integration.helpers.common import wait_for, wait_for_reconcile
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
    # will interfere with the tunnel from the runner to the mock jobmanager.
    return 8000


@pytest.fixture(scope="session")
def httpserver_listen_address(httpserver_listen_port: int):
    return ("0.0.0.0", httpserver_listen_port)


@pytest.fixture(scope="session", name="jobmanager_ip_address")
def jb_ip_address_fixture() -> str:
    """IP address for the jobmanager tests."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use as the fake jobmanager: %s", ip_address)
    s.close()
    return ip_address


@pytest.fixture(scope="session", name="jobmanager_base_url")
def jobmanager_base_url_fixture(
    jobmanager_ip_address: str,
    httpserver_listen_port: int,
) -> str:
    """Jobmanager base URL for the tests."""
    return f"http://{jobmanager_ip_address}:{httpserver_listen_port}"


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    app_no_runner: Application,
    jobmanager_base_url: str,
    httpserver: HTTPServer,
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    app_for_jobmanager = app_no_runner

    await app_for_jobmanager.set_config(
        {RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL)}
    )
    await wait_for_reconcile(app_for_jobmanager, app_for_jobmanager.model)

    httpserver.clear_all_handlers()

    yield app_for_jobmanager

    # cleanup of any runner spawned
    await app_for_jobmanager.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL),
        }
    )
    await wait_for_reconcile(app_for_jobmanager, app_for_jobmanager.model)


@pytest_asyncio.fixture(name="app_for_reactive")
async def app_for_reactive_fixture(
    ops_test,
    juju: jubilant.Juju,
    app: Application,
    mongodb: Application,
    jobmanager_base_url: str,
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    app_for_reactive = app

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
            TOKEN_CONFIG_NAME: "",
            PATH_CONFIG_NAME: jobmanager_base_url,
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            RECONCILE_INTERVAL_CONFIG_NAME: "5",  # set to higher number as the default due to race condition killing reactive process
        }
    )
    await wait_for_reconcile(app_for_reactive, app_for_reactive.model)

    yield app_for_reactive

    juju.remove_relation(*relation)

    await app_for_reactive.set_config(
        {
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL),
        }
    )
    await wait_for_reconcile(app_for_reactive, app_for_reactive.model)


@pytest.mark.abort_on_fail
async def test_jobmanager(
    instance_helper: OpenStackInstanceHelper,
    app: Application,
    httpserver: HTTPServer,
    jobmanager_base_url: str,
    jobmanager_ip_address: str,
):
    """
    This is a full test for the happy path of the jobmanager.

    A fake http server will simulate all interactions with the jobmanager.

    The main steps in this test are:
     1. Change config to spawn a runner.
     2. The github-runner manager will register a runner on the jobmanager.
     3. The jobmanager will return a health response with "PENDING" status and not deletable.
     4. A tunnel will be prepared in the test so the reactive runner can get to the jobmanager.
        This is specific to this test and in production it should not be needed.
     5. After some time, the runner will hit the jobmanager health endpoint indicating
        IDLE status.
     6. The jobmanager will change the health response to "IN_PROGRESS" and will send a job
        to the builder-agent. The job will be a sleep 30 seconds.
     7. The builder-agent will run the job. While running the job it will send the status
        EXECUTING and after it is finished it will send the status FINISHED.
     8. Run reconcile in the github-runner manager. As the jobmanager fake health response is
        still "IN_PROGRESS" and not deletable, the runner should not be deleted.
     9. Change the health response from the fake jobmanager to reply COMPLETED and deletable.
     10. Run reconcile in the github-runner manager. The runner should be deleted at this point.
    """
    # The http server simulates the jobmanager. Both the github-runner application
    # and the builder-agent will interact with the jobmanager. An alternative is
    # to create a test with a real jobmanager, and this could be done in the future.
    runner_id = 1234
    runner_token = "token"
    runner_health_path = f"/v1/runner/{runner_id}/health"

    # The builder-agent can get to us at any point after runner is spawned, so we already
    # register the health endpoint.
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="IDLE"
    )

    unit = app.units[0]

    # 1. Change config to spawn a runner.
    await app.set_config(
        {
            TOKEN_CONFIG_NAME: "",
            PATH_CONFIG_NAME: jobmanager_base_url,
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0",
        }
    )

    #  2. The github-runner manager will register a runner on the jobmanager.
    await _wait_for_runner_to_be_registered(httpserver, runner_id, runner_token)

    # 3. The jobmanager will return a health response with "PENDING" status and not deletable.
    runner_health_endpoint = GetRunnerHealthEndpoint(httpserver, runner_health_path)
    runner_health_endpoint.set(status="PENDING", deletable=False)

    # 4.  A tunnel will be prepared in the test so the reactive runner can get to the jobmanager.
    #         This is specific to this test and in production it should not be needed.
    async def _prepare_runner() -> bool:
        """Prepare the tunner so the runner builder-agent can get to the jobmanager."""
        return await _prepare_runner_tunnel_for_builder_agent(
            instance_helper, unit, jobmanager_ip_address, httpserver.port
        )

    await wait_for(_prepare_runner, check_interval=10, timeout=600)

    # 5. After some time, the runner will hit the jobmanager health endpoint indicating
    #   IDLE status.
    # httpserver.wait will only check for oneshot requests, so we register as oneshot handler.
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="IDLE", oneshot=True
    )

    with httpserver.wait(raise_assertions=True, stop_on_nohandler=False, timeout=120) as waiting:
        logger.info("Waiting for builder-agent to contact us.")
    logger.info("server log after executing: %s ", (httpserver.log))
    assert waiting.result, "builder-agent did not contact us with IDLE status."

    # 6. The jobmanager will change the health response to "IN_PROGRESS" and will send a job
    #         to the builder-agent. The job will be a sleep 30 seconds.
    runner_health_endpoint.set(status="IN_PROGRESS", deletable=False)

    # Ok, at this point, we want to tell the builder-agent to execute some command,
    # specifically a sleep so we can check that it goes over executing and finished statuses.
    await _execute_command_with_builder_agent(instance_helper, unit, "sleep 30")

    # 7. The builder-agent will run the job. While running the job it will send the status
    #         EXECUTING and after it is finished it will send the status FINISHED.
    # We need oneshot for httpserver.wait
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="EXECUTING", oneshot=True
    )
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="EXECUTING", oneshot=False
    )
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="FINISHED", oneshot=True
    )
    _add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="FINISHED", oneshot=False
    )

    with httpserver.wait(raise_assertions=True, stop_on_nohandler=False, timeout=120) as waiting:
        logger.info("Waiting for builder-agent to contact us.")
    logger.info("server log after executing: %s ", (httpserver.log))
    assert waiting.result, "builder-agent did not execute or finished."

    #      8. Run reconcile in the github-runner manager. As the jobmanager fake health response is
    #         still "IN_PROGRESS" and not deletable, the runner should not be deleted.
    logger.info("First reconcile that should not delete the runner, as it is still healthy.")
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app.set_config({RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL + 1)})
    await wait_for_reconcile(app, app.model)

    # At this point there should be a runner
    await _assert_runners(app, online=1, busy=1, offline=0, unknown=0)

    # 9. Change the health response from the fake jobmanager to reply COMPLETED and deletable.
    runner_health_endpoint.set(status="COMPLETED", deletable=True)

    # 10. Run reconcile in the github-runner manager. The runner should be deleted at this point.
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app.set_config({RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL + 2)})
    await wait_for_reconcile(app, app.model)

    await _assert_runners(app, online=0, busy=0, offline=0, unknown=0)


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
    runner_health_path = f"/v1/runner/{runner_id}/health"

    # The builder-agent can get to us at any point.
    _add_builder_agent_health_endpoint_response(
        app_for_reactive, httpserver, runner_health_path, runner_token, status="IDLE"
    )
    _add_builder_agent_health_endpoint_response(
        app_for_reactive, httpserver, runner_health_path, runner_token, status="EXECUTING"
    )
    _add_builder_agent_health_endpoint_response(
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
    await _wait_for_runner_to_be_registered(httpserver, runner_id, runner_token)

    # For the github runner manager, at this point, the jobmanager will return
    # that the runner health is pending and not deletable
    runner_health_endpoint = GetRunnerHealthEndpoint(httpserver, runner_health_path)
    runner_health_endpoint.set(status="PENDING", deletable=False)

    unit = app_for_reactive.units[0]

    async def _prepare_runner() -> bool:
        """Prepare the tunner so the runner builder-agent can get to the jobmanager."""
        return await _prepare_runner_tunnel_for_builder_agent(
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
    await wait_for_reconcile(app_for_reactive, app_for_reactive.model)

    # 6. Assert queue is empty
    assert_queue_is_empty(mongodb_uri, app_for_reactive.name)


def _add_builder_agent_health_endpoint_response(
    app, httpserver, runner_health_path, runner_token, status="IDLE", oneshot=False
):
    """Add a response to the builder-agent health endpoint for given status."""
    base_builder_agent_health_request = {
        "uri": runner_health_path,
        "method": "PUT",
        "headers": {"Authorization": f"Bearer {runner_token}"},
    }
    json_data = {"json": {"label": app.name, "status": status}}
    builder_agent_request_parms = base_builder_agent_health_request | json_data
    if oneshot:
        httpserver.expect_oneshot_request(**builder_agent_request_parms).respond_with_data("OK")
    else:
        httpserver.expect_request(**builder_agent_request_parms).respond_with_data("OK")


async def _assert_runners(app: Application, online: int, busy: int, offline: int, unknown: int):
    """Assert the number of runners with given status in the application."""
    action = await app.units[0].run_action("check-runners")
    await action.wait()
    logger.info("check-runners: %s", action.results)
    assert action.status == "completed"
    assert action.results["online"] == str(online), f"{online} Runner(s) should be online"
    assert action.results["busy"] == str(busy), f"{busy} Runner(s) should be busy"
    assert action.results["offline"] == str(offline), f"{offline} Runner(s) should be offline"
    assert action.results["unknown"] == str(unknown), f"{unknown} Runner(s) should be unknown"


class GetRunnerHealthEndpoint:
    """Class modelling the runner health endpoint."""

    def __init__(self, httpserver: HTTPServer, runner_health_path: str):
        """Initialize the GetRunnerHealthEndpoint.

        Args:
            httpserver: The HTTP server to use for the endpoint.
            runner_health_path: The path for the runner health endpoint.
        """
        self.httpserver = httpserver
        self.runner_health_path = runner_health_path
        self._handler: RequestHandler | None = None

    def set(self, status="PENDING", deletable=False):
        """Set the runner health endpoint.

        Args:
            status: The status of the runner, e.g., "PENDING", "IDLE", "IN_PROGRESS", "COMPLETED".
            deletable: Whether the runner is deletable or not.
        """
        # '/v1/runner/<runner_id>/health', 'GET',
        # Returns GetRunnerHealthV1RunnerRunnerIdHealthGet200Response
        health_response = GetRunnerHealthV1RunnerRunnerIdHealthGet200Response(
            label="label",
            cpu_usage="1",
            ram_usage="1",
            disk_usage="1",
            status=status,
            deletable=deletable,
        )
        if not self._handler:
            self._handler = self.httpserver.expect_request(
                uri=self.runner_health_path, method="GET"
            )
        self._handler.respond_with_json(health_response.to_dict())
        logger.info("handler health %s", self._handler)


async def _wait_for_runner_to_be_registered(httpserver, runner_id: int, runner_token: str):
    """Wait for the runner to be registered in the jobmanager."""
    runner_register = "/v1/runner/register"
    returned_token = RegisterRunnerV1RunnerRegisterPost200Response(
        id=runner_id, token=runner_token
    )
    httpserver.expect_oneshot_request(runner_register).respond_with_json(returned_token.to_dict())
    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for runner to be registered.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed waiting for get token in the jobmanager."


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
    logger.info("prepared tunnel for builder agent")
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
