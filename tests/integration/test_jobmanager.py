# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import asyncio
import logging
import socket
from typing import AsyncIterator

import pytest
import pytest_asyncio
from juju.application import Application
from pytest_httpserver import HTTPServer

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
from jobmanager.client.jobmanager_client.models.register_runner_v1_runner_register_post200_response import (
    RegisterRunnerV1RunnerRegisterPost200Response,
)
from tests.integration.helpers.common import wait_for, wait_for_reconcile
from tests.integration.helpers.openstack import OpenStackInstanceHelper, PrivateEndpointConfigs

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
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    app_for_jobmanager = app_no_runner

    yield app_for_jobmanager

    # cleanup of any runner spawned
    await app_for_jobmanager.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await wait_for_reconcile(app_for_jobmanager, app_for_jobmanager.model)


@pytest.mark.abort_on_fail
async def test_jobmanager(
    monkeypatch: pytest.MonkeyPatch,
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
    runner_register = "/v1/runner/register"
    returned_token = RegisterRunnerV1RunnerRegisterPost200Response(
        id=runner_id, token=runner_token
    )
    httpserver.expect_oneshot_request(runner_register).respond_with_json(returned_token.to_dict())

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for runner to be registered.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed waiting for get token in the jobmanager."

    # 3. The jobmanager will return a health response with "PENDING" status and not deletable.
    # '/v1/runner/<runner_id>/health', 'GET',
    # Returns GetRunnerHealthV1RunnerRunnerIdHealthGet200Response
    health_response = GetRunnerHealthV1RunnerRunnerIdHealthGet200Response(
        label="label",
        cpu_usage="1",
        ram_usage="1",
        disk_usage="1",
        status="PENDING",
        deletable=False,
    )
    health_get_handler = httpserver.expect_request(uri=runner_health_path, method="GET")
    health_get_handler.respond_with_json(health_response.to_dict())

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
    runner_health_path = f"/v1/runner/{runner_id}/health"
    base_builder_agent_health_request = {
        "uri": runner_health_path,
        "method": "PUT",
        "headers": {"Authorization": f"Bearer {runner_token}"},
    }
    json_idle = {"json": {"label": app.name, "status": "IDLE"}}
    # httpserver.wait will only check for oneshot requeusts, so we register both a oneshot
    # and a normal request to the same endpoint. Order is important here, we first need to
    # register the oneshot request, so it will be executed first, and then the normal request.
    httpserver.expect_oneshot_request(
        **base_builder_agent_health_request | json_idle
    ).respond_with_data("OK")
    httpserver.expect_request(**base_builder_agent_health_request | json_idle).respond_with_data(
        "OK"
    )

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=120) as waiting:
        logger.info("Waiting for builder-agent to contact us.")
    logger.info("server log after executing: %s ", (httpserver.log))

    # 6. The jobmanager will change the health response to "IN_PROGRESS" and will send a job
    #         to the builder-agent. The job will be a sleep 30 seconds.
    health_response.status = "IN_PROGRESS"
    health_response.deletable = False
    health_get_handler.respond_with_json(health_response.to_dict())

    httpserver.check_assertions()

    unit = app.units[0]
    # Ok, at this point, we want to tell the builder-agent to execute some command,
    # specifically a sleep so we can check that it goes over executing and finished statuses.
    await _execute_command_with_builder_agent(instance_helper, unit, "sleep 30")

    # 7. The builder-agent will run the job. While running the job it will send the status
    #         EXECUTING and after it is finished it will send the status FINISHED.
    json_executing = {"json": {"label": app.name, "status": "EXECUTING"}}
    json_finished = {"json": {"label": app.name, "status": "FINISHED"}}
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

    #      8. Run reconcile in the github-runner manager. As the jobmanager fake health response is
    #         still "IN_PROGRESS" and not deletable, the runner should not be deleted.
    logger.info("First reconcile that should not delete the runner, as it is still healthy.")
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app.set_config({RECONCILE_INTERVAL_CONFIG_NAME: "10"})
    await wait_for_reconcile(app, app.model)

    # At this point there should be a runner
    action = await app.units[0].run_action("check-runners")
    await action.wait()
    logger.info("check-runners after first reconcile: %s", action.results)
    assert action.status == "completed"
    assert action.results["online"] == "1", "Runner should be online after first reconcile"
    assert action.results["busy"] == "1", "Runner should be busy after first reconcile"
    assert action.results["offline"] == "0", "Runner should not be offline after first reconcile"
    assert action.results["unknown"] == "0", "Runner should not be unknown after first reconcile"

    logger.info("handlers %s", httpserver.format_matchers())
    logger.info("handler health %s", health_get_handler)

    # 9. Change the health response from the fake jobmanager to reply COMPLETED and deletable.
    health_response.deletable = True
    health_response.status = "COMPLETED"
    health_get_handler.respond_with_json(health_response.to_dict())
    logger.info("handler health %s", health_get_handler)
    logger.info("handlers %s", httpserver.format_matchers())

    # 10. Run reconcile in the github-runner manager. The runner should be deleted at this point.
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app.set_config({RECONCILE_INTERVAL_CONFIG_NAME: "5"})
    await wait_for_reconcile(app, app.model)

    action = await app.units[0].run_action("check-runners")
    await action.wait()
    logger.info("check-runner runners after second reconcile: %s", action.results)
    assert action.status == "completed"
    assert action.results["online"] == "0", "No runners should be online after second reconcile"
    assert action.results["busy"] == "0", "No runners should be busy after second reconcile"
    assert action.results["offline"] == "0", "No runners should be offline after second reconcile"
    assert action.results["unknown"] == "0", "No runners should be unknown after second reconcile"


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
