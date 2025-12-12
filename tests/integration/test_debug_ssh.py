# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import logging

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.common import dispatch_workflow, get_job_logs
from tests.integration.helpers.openstack import OpenStackInstanceHelper
from tests.status_name import ACTIVE

logger = logging.getLogger(__name__)

SSH_DEBUG_WORKFLOW_FILE_NAME = "workflow_dispatch_ssh_debug.yaml"

pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(scope="module", name="app_no_wait_tmate")
async def app_no_wait_tmate_fixture(
    model: Model,
    app_openstack_runner,
    tmate_ssh_server_app: Application,
):
    """Application to check tmate ssh with openstack without waiting for active."""
    application = app_openstack_runner
    await application.relate("debug-ssh", f"{tmate_ssh_server_app.name}:debug-ssh")
    await application.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await model.wait_for_idle(apps=[tmate_ssh_server_app.name], status=ACTIVE, timeout=60 * 30)
    return application


async def test_ssh_debug(
    app_no_wait_tmate: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    tmate_ssh_server_unit_ip: str,
    instance_helper: OpenStackInstanceHelper,
):
    """
    arrange: given an integrated GitHub-Runner charm and tmate-ssh-server charm.
    act: when canonical/action-tmate is triggered.
    assert: the ssh connection info from action-log and tmate-ssh-server matches.
    """
    await instance_helper.ensure_charm_has_runner(app_no_wait_tmate)

    unit = app_no_wait_tmate.units[0]
    # We need the runner to connect to the current machine, instead of the tmate_ssh_server unit,
    # as the tmate_ssh_server is not routable.
    dnat_command_in_runner = f"sudo iptables -t nat -A OUTPUT -p tcp -d {tmate_ssh_server_unit_ip} --dport 10022 -j DNAT --to-destination 127.0.0.1:10022"
    _, _, _ = await instance_helper.run_in_instance(
        unit,
        dnat_command_in_runner,
        assert_on_failure=True,
    )
    await instance_helper.expose_to_instance(unit=unit, port=10022, host=tmate_ssh_server_unit_ip)

    # trigger tmate action
    logger.info("Dispatching workflow_dispatch_ssh_debug.yaml workflow.")

    # expect failure since the ssh workflow will timeout
    workflow_run = await dispatch_workflow(
        app=app_no_wait_tmate,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="failure",
        workflow_id_or_name=SSH_DEBUG_WORKFLOW_FILE_NAME,
    )

    logs = get_job_logs(workflow_run.jobs("latest")[0])

    # ensure ssh connection info printed in logs.
    logger.info("Logs: %s", logs)
    assert tmate_ssh_server_unit_ip in logs, "Tmate ssh server IP not found in action logs."
    assert "10022" in logs, "Tmate ssh server connection port not found in action logs."
