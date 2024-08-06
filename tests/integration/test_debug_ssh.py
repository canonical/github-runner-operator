# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import logging

from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import DENYLIST_CONFIG_NAME
from tests.integration.helpers.common import dispatch_workflow, get_job_logs
from tests.status_name import ACTIVE

logger = logging.getLogger(__name__)

SSH_DEBUG_WORKFLOW_FILE_NAME = "workflow_dispatch_ssh_debug.yaml"


async def test_ssh_debug(
    model: Model,
    app_no_wait: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    tmate_ssh_server_unit_ip: str,
):
    """
    arrange: given an integrated GitHub-Runner charm and tmate-ssh-server charm with a denylist \
        covering ip ranges of tmate-ssh-server.
    act: when canonical/action-tmate is triggered.
    assert: the ssh connection info from action-log and tmate-ssh-server matches.
    """
    await app_no_wait.set_config(
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

    # trigger tmate action
    logger.info("Dispatching workflow_dispatch_ssh_debug.yaml workflow.")

    # expect failure since the ssh workflow will timeout
    workflow_run = await dispatch_workflow(
        app=app_no_wait,
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
