# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with ssh-debug integration."""
import zipfile
from io import BytesIO

import requests
from github.Branch import Branch
from github.Repository import Repository
from github.Workflow import Workflow

from tests.integration.helpers import wait_for


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
    workflow: Workflow = github_repository.get_workflow("workflow_dispatch_ssh_debug.yaml")
    workflow.create_dispatch(test_github_branch, inputs={"runner": app_name})

    # get action logs
    last_run = workflow.get_runs()[0]

    def is_workflow_complete():
        """Return if the workflow is complete."""
        last_run.update()
        return last_run.status == "completed"

    await wait_for(is_workflow_complete)

    response = requests.get(
        last_run.logs_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    zip_data = BytesIO(response.content)
    with zipfile.ZipFile(zip_data, "r") as zip_ref:
        tmate_log_filename = next(
            iter([name for name in zip_ref.namelist() if "Setup tmate session" in name])
        )
        logs = str(zip_ref.read(tmate_log_filename), encoding="utf-8")

    # ensure ssh connection info printed in logs.
    assert tmate_ssh_server_unit_ip in logs, "Tmate ssh server IP not found in action logs."
    assert "10022" in logs, "Tmate ssh server connection port not found in action logs."
