# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import logging
from datetime import datetime, timezone

from github.Branch import Branch
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from juju.application import Application

from tests.integration.charm_metrics_helpers import (
    _get_job_logs,
    dispatch_workflow,
    get_workflow_runs,
)

logger = logging.getLogger(__name__)

SSH_DEBUG_WORKFLOW_FILE_NAME = "workflow_dispatch_ssh_debug.yaml"


async def test_ssh_debug(
    app_no_wait: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    tmate_ssh_server_unit_ip: str,
):
    """
    arrange: given an integrated GitHub-Runner charm and tmate-ssh-server charm.
    act: when canonical/action-tmate is triggered.
    assert: the ssh connection info from action-log and tmate-ssh-server matches.
    """
    # trigger tmate action
    logger.info("Dispatching workflow_dispatch_ssh_debug.yaml workflow.")
    start_time = datetime.now(timezone.utc)

    # expect failure since the ssh workflow will timeout
    workflow = await dispatch_workflow(
        app=app_no_wait,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="failure",
        workflow_id_or_name=SSH_DEBUG_WORKFLOW_FILE_NAME,
    )

    latest_run: WorkflowRun = next(
        get_workflow_runs(
            start_time=start_time,
            workflow=workflow,
            runner_name=app_no_wait.name,
            branch=test_github_branch,
        )
    )

    logs = _get_job_logs(latest_run.jobs("latest")[0])

    # ensure ssh connection info printed in logs.
    logger.info("Logs: %s", logs)
    assert tmate_ssh_server_unit_ip in logs, "Tmate ssh server IP not found in action logs."
    assert "10022" in logs, "Tmate ssh server connection port not found in action logs."
