# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import logging
import typing
import zipfile
from io import BytesIO

import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun

from tests.integration.helpers import wait_for

logger = logging.getLogger(__name__)


async def test_ssh_debug(
    github_repository: Repository,
    test_github_branch: Branch,
    app_name: str,
    token: str,
    tmate_ssh_server_unit_ip: str,
):
    """
    arrange: given an integrated GitHub-Runner charm and tmate-ssh-server charm.
    act: when canonical/action-tmate is triggered.
    assert: the ssh connection info from action-log and tmate-ssh-server matches.
    """
    # trigger tmate action
    logger.info("Dispatching workflow_dispatch_ssh_debug.yaml workflow.")
    workflow: Workflow = github_repository.get_workflow("workflow_dispatch_ssh_debug.yaml")
    assert workflow.create_dispatch(
        test_github_branch, inputs={"runner": app_name}
    ), "Failed to dispatch workflow"

    # get action logs
    def latest_workflow_run() -> typing.Optional[WorkflowRun]:
        """Get latest workflow run."""
        try:
            logger.info("Fetching latest workflow run on branch %s.", test_github_branch.name)
            # The test branch is unique per test, hence there can only be one run per branch.
            last_run: WorkflowRun = workflow.get_runs(branch=test_github_branch)[0]
        except IndexError:
            return None
        return last_run

    await wait_for(latest_workflow_run, timeout=60 * 10, check_interval=60)
    lastest_run = typing.cast(WorkflowRun, latest_workflow_run())

    def is_workflow_complete():
        """Return if the workflow is complete."""
        lastest_run.update()
        logger.info("Fetched latest workflow status %s.", lastest_run.status)
        return lastest_run.status == "completed"

    await wait_for(is_workflow_complete, timeout=60 * 45, check_interval=60)

    response = requests.get(
        lastest_run.logs_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    zip_data = BytesIO(response.content)
    with zipfile.ZipFile(zip_data, "r") as zip_ref:
        logger.info("Files: %s", zip_ref.namelist())
        tmate_log_filename = next(
            iter(
                [
                    name
                    for name in zip_ref.namelist()
                    if "workflow-dispatch-tests/3_Setup tmate session.txt" == name
                ]
            )
        )
        logs = str(zip_ref.read(tmate_log_filename), encoding="utf-8")

    # ensure ssh connection info printed in logs.
    logger.info("Logs: %s", logs)
    assert tmate_ssh_server_unit_ip in logs, "Tmate ssh server IP not found in action logs."
    assert "10022" in logs, "Tmate ssh server connection port not found in action logs."
