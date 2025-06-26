#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import logging

import pytest
from juju.application import Application
from pytest_httpserver import HTTPServer

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
)
from tests.integration.conftest import DEFAULT_RECONCILE_INTERVAL
from tests.integration.helpers.common import wait_for, wait_for_reconcile, wait_for_runner_ready
from tests.integration.helpers.openstack import OpenStackInstanceHelper
from tests.integration.jobmanager.helpers import (
    GetRunnerHealthEndpoint,
    _assert_runners,
    _execute_command_with_builder_agent,
    add_builder_agent_health_endpoint_response,
    prepare_runner_tunnel_for_builder_agent,
    wait_for_runner_to_be_registered,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.openstack


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
    runner_health_path = f"/v1/runners/{runner_id}/health"

    # The builder-agent can get to us at any point after runner is spawned, so we already
    # register the health endpoint.
    add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="IDLE"
    )

    unit = app.units[0]

    # 1. Change config to spawn a runner.
    await app.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0",
        }
    )

    #  2. The github-runner manager will register a runner on the jobmanager.
    await wait_for_runner_to_be_registered(httpserver, runner_id, runner_token)

    # 3. The jobmanager will return a health response with "PENDING" status and not deletable.
    runner_health_endpoint = GetRunnerHealthEndpoint(httpserver, runner_health_path)
    runner_health_endpoint.set(status="PENDING", deletable=False)

    # 4.  A tunnel will be prepared in the test so the reactive runner can get to the jobmanager.
    #         This is specific to this test and in production it should not be needed.
    async def _prepare_runner() -> bool:
        """Prepare the tunner so the runner builder-agent can get to the jobmanager."""
        return await prepare_runner_tunnel_for_builder_agent(
            instance_helper, unit, jobmanager_ip_address, httpserver.port
        )

    await wait_for(_prepare_runner, check_interval=10, timeout=600)

    # 5. After some time, the runner will hit the jobmanager health endpoint indicating
    #   IDLE status.
    # httpserver.wait will only check for oneshot requests, so we register as oneshot handler.
    add_builder_agent_health_endpoint_response(
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
    add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="EXECUTING", oneshot=True
    )
    add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="EXECUTING", oneshot=False
    )
    add_builder_agent_health_endpoint_response(
        app, httpserver, runner_health_path, runner_token, status="FINISHED", oneshot=True
    )
    add_builder_agent_health_endpoint_response(
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
    await wait_for_runner_ready(app)

    # At this point there should be a runner
    await _assert_runners(app, online=1, busy=1, offline=0, unknown=0)

    # 9. Change the health response from the fake jobmanager to reply COMPLETED and deletable.
    runner_health_endpoint.set(status="COMPLETED", deletable=True)

    # 10. Run reconcile in the github-runner manager. The runner should be deleted at this point.
    # TMP: hack to trigger reconcile by changing the configuration, which cause config_changed hook
    # to restart the reconcile service.
    await app.set_config({RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL + 2)})
    await wait_for_reconcile(app)

    await _assert_runners(app, online=0, busy=0, offline=0, unknown=0)
