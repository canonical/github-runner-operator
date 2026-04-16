# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

Tests a path change in the repo.
"""

import logging

import jubilant
import pytest
from github.Repository import Repository

from charm_state import PATH_CONFIG_NAME
from tests.integration.conftest import GitHubConfig
from tests.integration.helpers.common import wait_for_runner_ready
from tests.integration.helpers.openstack import OpenStackInstanceHelper

logger = logging.getLogger(__name__)


@pytest.mark.openstack
@pytest.mark.abort_on_fail
def test_path_config_change(
    juju: jubilant.Juju,
    app_with_forked_repo: str,
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
        lambda status: jubilant.all_active(status, app_with_forked_repo),
        delay=10,
        timeout=10 * 60,
    )

    logger.info("Ensure there is a runner (this calls reconcile)")
    instance_helper.ensure_charm_has_runner(app_with_forked_repo)

    juju.config(app_with_forked_repo, values={PATH_CONFIG_NAME: github_config.path}, log=False)

    logger.info("Reconciling (again)")
    wait_for_runner_ready(juju, app_with_forked_repo)

    unit_name = f"{app_with_forked_repo}/0"
    runner_names = instance_helper.get_runner_names(unit_name)
    logger.info("runners: %s", runner_names)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()
    logger.info("runners in github repo: %s", list(runners_in_repo))

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
