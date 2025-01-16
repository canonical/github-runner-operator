# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import logging

import pytest
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import DENYLIST_CONFIG_NAME
from tests.integration.helpers.common import InstanceHelper, dispatch_workflow, get_job_logs
from tests.status_name import ACTIVE

logger = logging.getLogger(__name__)

SSH_DEBUG_WORKFLOW_FILE_NAME = "workflow_dispatch_ssh_debug.yaml"

pytestmark = pytest.mark.openstack


async def test_ssh_debug(
    model: Model,
    app_no_wait_tmate: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    tmate_ssh_server_unit_ip: str,
    instance_helper: InstanceHelper,
):
    """
    arrange: given an integrated GitHub-Runner charm and tmate-ssh-server charm with a denylist \
        covering ip ranges of tmate-ssh-server.
    act: when canonical/action-tmate is triggered.
    assert: the ssh connection info from action-log and tmate-ssh-server matches.
    """
    await app_no_wait_tmate.set_config(
        {
            DENYLIST_CONFIG_NAME: (
                "0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,169.254.0.0/16,"
                "172.16.0.0/12,192.0.0.0/24,192.0.2.0/24,192.88.99.0/24,192.168.0.0/16,"
                "198.18.0.0/15,198.51.100.0/24,203.0.113.0/24,224.0.0.0/4,233.252.0.0/24,"
                "240.0.0.0/4"
            ),
        }
    )
    await model.wait_for_idle(status=ACTIVE, timeout=60 * 120)

    unit = app_no_wait_tmate.units[0]
    # We need the runner to connect to the current machine, instead of the tmate_ssh_server unit,
    # as the tmate_ssh_server is not routable.
    dnat_comman_in_runner = "sudo iptables -t nat -A OUTPUT -p tcp --dport 10022 -j DNAT --to-destination 127.0.0.1:10022"
    _, _, _ = await instance_helper.run_in_instance(
        unit,
        dnat_comman_in_runner,
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
