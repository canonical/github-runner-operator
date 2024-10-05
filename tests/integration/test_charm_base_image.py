# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""

from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import BASE_IMAGE_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
    dispatch_workflow,
    wait_for,
)
from tests.integration.helpers.lxd import (
    ensure_charm_has_runner,
    get_runner_name,
    run_in_lxd_instance,
)


async def test_runner_base_image(
    model: Model,
    app_no_wait: Application,
    github_repository: Repository,
    test_github_branch: Branch,
) -> None:
    """
    arrange: A runner with noble as base image.
    act: Dispatch a workflow.
    assert: A runner is created with noble OS base and the workflow job is successfully run.
    """
    await app_no_wait.set_config(
        {
            BASE_IMAGE_CONFIG_NAME: "noble",
        }
    )
    await model.wait_for_idle(apps=[app_no_wait.name], timeout=35 * 60)
    await ensure_charm_has_runner(app_no_wait, model)

    #  Runner with noble base image is created
    unit = app_no_wait.units[0]
    runner_name = await get_runner_name(unit)
    code, stdout, stderr = await run_in_lxd_instance(unit, runner_name, "lsb_release -a")
    assert code == 0, f"Unable to get release name, {stdout} {stderr}"
    assert "noble" in str(stdout)

    # Workflow completes successfully
    await dispatch_workflow(
        app=app_no_wait,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_E2E_TEST_RUN_WORKFLOW_FILENAME,
        dispatch_input={"runner-tag": app_no_wait.name, "runner-virt-type": "lxd"},
    )
