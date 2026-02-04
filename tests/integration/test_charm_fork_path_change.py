# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

Tests a path change in the repo.
"""

import logging

import jubilant
import pytest
from github.Repository import Repository
from juju.application import Application

from charm_state import PATH_CONFIG_NAME
from tests.integration.conftest import GitHubConfig
from tests.integration.helpers.common import wait_for_runner_ready
from tests.integration.helpers.openstack import OpenStackInstanceHelper

logger = logging.getLogger(__name__)


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_path_config_change(
    juju: jubilant.Juju,
    app_with_forked_repo: Application,
    github_repository: Repository,
    github_config: GitHubConfig,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with one runner in a forked repository.
    act: Change the path configuration to the main repository and reconcile runners.
    assert: No runners connected to the forked repository and one runner in the main repository.
    """
    logger.info("test_path_config_change")
    juju.wait(
        lambda status: jubilant.all_active(status, app_with_forked_repo.name),
        delay=10,
        timeout=10 * 60,
    )

    unit = app_with_forked_repo.units[0]

    logger.info("Ensure there is a runner (this calls reconcile)")
    await instance_helper.ensure_charm_has_runner(app_with_forked_repo)

    juju.config(app_with_forked_repo.name, values={PATH_CONFIG_NAME: github_config.path})

    logger.info("Reconciling (again)")
    await wait_for_runner_ready(app=app_with_forked_repo)

    runner_names = await instance_helper.get_runner_names(unit)
    logger.info("runners: %s", runner_names)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()
    logger.info("runners in github repo: %s", list(runners_in_repo))

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
