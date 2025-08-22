#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

import asyncio
import logging

from juju.application import Application
from pytest_httpserver import HTTPServer, RequestHandler

from jobmanager.client.jobmanager_client.models.runner_health_response import RunnerHealthResponse
from jobmanager.client.jobmanager_client.models.runner_register_response import (
    RunnerRegisterResponse,
)

logger = logging.getLogger(__name__)


def add_builder_agent_health_endpoint_response(
    app: Application,
    httpserver: HTTPServer,
    runner_health_path: str,
    runner_token: str,
    status="IDLE",
    oneshot=False,
):
    """Add a response to the builder-agent health endpoint for given status.

    Args:
        app: The application to which the builder-agent belongs.
        httpserver: The HTTP server to use for the endpoint.
        runner_health_path: The path for the runner health endpoint.
        runner_token: The token for the runner.
        status: The status of the runner, e.g., "IDLE", "IN_PROGRESS", "COMPLETED".
        oneshot: If True, the request will be expected only once.
    """
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
    """Assert the number of runners with given status in the application.

    Args:
        app: The application to check the runners in.
        online: The expected number of online runners.
        busy: The expected number of busy runners.
        offline: The expected number of offline runners.
        unknown: The expected number of unknown runners.
    """
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

    def __init__(self, httpserver: HTTPServer, runner_health_path: str, jobmanager_token: str):
        """Initialize the GetRunnerHealthEndpoint.

        Args:
            httpserver: The HTTP server to use for the endpoint.
            runner_health_path: The path for the runner health endpoint.
            jobmanager_token: The token for the jobmanager for authentication.
        """
        self.httpserver = httpserver
        self.runner_health_path = runner_health_path
        self._handler: RequestHandler | None = None
        self._jobmanager_token = jobmanager_token

    def set(self, status="PENDING", deletable=False):
        """Set the runner health endpoint.

        Args:
            status: The status of the runner, e.g., "PENDING", "IDLE", "IN_PROGRESS", "COMPLETED".
            deletable: Whether the runner is deletable or not.
        """
        # '/v1/runners/<runner_id>/health', 'GET',
        # Returns GetRunnerHealthV1RunnerRunnerIdHealthGet200Response
        health_response = RunnerHealthResponse(
            label="label",
            cpu_usage="1",
            ram_usage="1",
            disk_usage="1",
            status=status,
            deletable=deletable,
        )
        if not self._handler:
            self._handler = self.httpserver.expect_request(
                uri=self.runner_health_path,
                method="GET",
                headers={"Authorization": f"Bearer {self._jobmanager_token}"},
            )
        self._handler.respond_with_json(health_response.to_dict())
        logger.info("handler health %s", self._handler)


async def wait_for_runner_to_be_registered(
    httpserver: HTTPServer, runner_id: int, runner_token: str, jobmanager_token: str
):
    """Wait for the runner to be registered in the jobmanager.

    Args:
        httpserver: The HTTP server to use for the request.
        runner_id: The ID of the runner.
        runner_token: The token of the runner.
        jobmanager_token: The token for authentication with the jobmanager.
    """
    runner_register = "/v1/runners/register"
    returned_token = RunnerRegisterResponse(id=runner_id, token=runner_token)
    httpserver.expect_oneshot_request(
        uri=runner_register,
        method="POST",
        headers={
            "Authorization": f"Bearer {jobmanager_token}",
        },
    ).respond_with_json(returned_token.to_dict())
    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=30) as waiting:
        logger.info("Waiting for runner to be registered.")
    logger.info("server log: %s ", (httpserver.log))
    assert waiting.result, "Failed waiting for get token in the jobmanager."


async def prepare_runner_tunnel_for_builder_agent(
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

    Args:
        instance_helper: An instance helper to run commands in the unit.
        unit: The unit where the runner is running.
        jobmanager_address: The address of the jobmanager.
        jobmanager_port: The port of the jobmanager.

    Returns:
        bool: True if the tunnel was prepared successfully, False otherwise.
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


async def execute_command_with_builder_agent(instance_helper, unit, command) -> None:
    """Execute a command in the builder-agent.

    Args:
        instance_helper: Helper class to manage interactions with OpenStack instances.
        unit: The Juju unit to operate on.
        command: The command to run.
    """
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
