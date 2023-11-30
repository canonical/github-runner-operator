# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for self-hosted runner managed by the github-runner charm."""

from datetime import datetime, timezone
from time import sleep

import github
import pytest
import requests
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    get_runner_names,
    run_in_lxd_instance,
)
from tests.status_name import ACTIVE_STATUS_NAME


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dispatch_workflow_with_dockerhub_mirror(
    model: Model, app_runner: Application, github_repository: Repository
) -> None:
    """
    arrange: A working application with no runners.
    act:
        1. Set dockerhub-mirror config and spawn one runner.
        2. Dispatch a workflow.
    assert:
        1. registry-mirrors is setup in /etc/docker/daemon.json of runner.
        2. Message about dockerhub_mirror appears in logs.
    """
    start_time = datetime.now(timezone.utc)

    unit = app_runner.units[0]

    fake_url = "https://example.com:5000"

    # 1.
    await app_runner.set_config({"virtual-machines": "1", "dockerhub-mirror": fake_url})
    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    names = await get_runner_names(unit)
    assert len(names) == 1

    runner_to_be_used = names[0]

    return_code, stdout = await run_in_lxd_instance(
        unit, runner_to_be_used, "cat /etc/docker/daemon.json"
    )
    assert return_code == 0
    assert stdout is not None
    assert "registry-mirrors" in stdout
    assert fake_url in stdout

    # 2.
    main_branch = github_repository.get_branch(github_repository.default_branch)
    workflow = github_repository.get_workflow(id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME)

    workflow.create_dispatch(main_branch, {"runner": app_runner.name})

    # Wait until the runner is used up.
    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner_to_be_used not in runners:
            break
        sleep(30)
    else:
        assert False, "Timeout while waiting for workflow to complete"

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore, all runs after this test start should pass the conditions.
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        if start_time > run.created_at:
            continue

        try:
            logs_url = run.jobs()[0].logs_url()
            logs = requests.get(logs_url).content.decode("utf-8")
        except github.GithubException.GithubException:
            continue

        if f"Job is about to start running on the runner: {app_runner.name}-" in logs:
            assert run.jobs()[0].conclusion == "success"
            assert (
                "A private docker registry is setup as a dockerhub mirror for this self-hosted"
                " runner."
            ) in logs
