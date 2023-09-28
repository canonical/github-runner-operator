# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with no runner."""

import pytest
from juju.application import Application
from juju.model import Model

from charm import GithubRunnerCharm
from tests.integration.helpers import (
    check_runner_binary_exists,
    get_repo_policy_compliance_pip_info,
    install_repo_policy_compliance_from_git_source,
    remove_runner_bin,
    run_in_unit,
    wait_till_num_of_runners,
)
from tests.status_name import ACTIVE_STATUS_NAME

REPO_POLICY_COMPLIANCE_VER_0_2_GIT_SOURCE = (
    "git+https://github.com/canonical/"
    "repo-policy-compliance@48b36c130b207278d20c3847ce651ac13fb9e9d7"
)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_dependencies_action_latest_service(
    model: Model, app_no_runner: Application
) -> None:
    """
    arrange: An working application with latest version of repo-policy-compliance service.
    act: Run update-dependencies action.
    assert:
        a. Service is installed in the charm.
        b. Action did not flushed the runners.
    """
    unit = app_no_runner.units[0]

    action = await unit.run_action("update-dependencies")
    await action.wait()
    assert action.results["flush"] == "False"

    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    assert await get_repo_policy_compliance_pip_info(unit) is not None


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_dependencies_action_no_service(
    model: Model, app_no_runner: Application
) -> None:
    """
    arrange: Remove repo-policy-compliance service installation.
    act: Run update-dependencies action.
    assert:
        a. Service is installed in the charm.
        b. Action flushed the runners.
    """
    unit = app_no_runner.units[0]

    await install_repo_policy_compliance_from_git_source(unit, None)
    assert await get_repo_policy_compliance_pip_info(unit) is None

    action = await unit.run_action("update-dependencies")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    assert action.results["flush"] == "True"
    assert await get_repo_policy_compliance_pip_info(unit) is not None


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_dependencies_action_old_service(
    model: Model, app_no_runner: Application
) -> None:
    """
    arrange: Replace repo-policy-compliance service installation to a older version.
    act: Run update-dependencies action.
    assert:
        a. Service is installed in the charm.
        b. Action flushed the runners.
    """
    unit = app_no_runner.units[0]
    latest_version_info = await get_repo_policy_compliance_pip_info(unit)

    await install_repo_policy_compliance_from_git_source(
        unit, REPO_POLICY_COMPLIANCE_VER_0_2_GIT_SOURCE
    )
    assert await get_repo_policy_compliance_pip_info(unit) != latest_version_info

    action = await unit.run_action("update-dependencies")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    assert action.results["flush"] == "True"
    assert await get_repo_policy_compliance_pip_info(unit) is not None


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_update_dependencies_action_on_runner_binary(
    model: Model, app_no_runner: Application
) -> None:
    """
    arrange: Remove runner binary if exists.
    act:
        1. Run update-dependencies action.
        2. Run update-dependencies action.
    assert:
        1.  a. Runner binary exists in the charm.
            b. Action flushed the runners.
        2.  a. Runner binary exists in the charm.
            b. Action did not flushed the runners.
    """
    unit = app_no_runner.units[0]

    await remove_runner_bin(unit)

    action = await unit.run_action("update-dependencies")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    # The runners should be flushed on update of runner binary.
    assert action.results["flush"] == "True"

    assert await check_runner_binary_exists(unit)

    action = await unit.run_action("update-dependencies")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    # The runners should be flushed on update of runner binary.
    assert action.results["flush"] == "False"

    assert await check_runner_binary_exists(unit)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runners_no_runners(app_no_runner: Application) -> None:
    """
    arrange: An working application with no runners.
    act: Run check-runners action.
    assert: Action returns result with no runner.
    """
    unit = app_no_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
    assert not action.results["runners"]


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_runners(model: Model, app_no_runner: Application) -> None:
    """
    arrange: An working application with no runners.
    act:
        1.  a. Set virtual-machines config to 1.
            b. Run reconcile_runners action.
        2.  a. Set virtual-machiens config to 0.
            b. Run reconcile_runners action.
    assert:
        1. One runner should exist.
        2. No runner should exist.

    The two test is combine to maintain no runners in the application after the
    test.
    """
    # Rename since the app will have a runner.
    app = app_no_runner

    unit = app.units[0]

    # 1.
    await app.set_config({"virtual-machines": "1"})

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    await wait_till_num_of_runners(unit, 1)

    # 2.
    await app.set_config({"virtual-machines": "0"})

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    await wait_till_num_of_runners(unit, 0)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_runners_with_lxd_storage_pool_failure(
    model: Model, app_no_runner: Application
) -> None:
    """
    arrange: An working application with no runners.
    act:
        1.  a. Delete content in the runner LXD storage directory.
            b. Set virtual-machines config to 1.
            c. Run reconcile_runners action.
        2.  a. Set virtual-machiens config to 0.
            b. Run reconcile_runners action.
    assert:
        1. One runner should exist.
        2. No runner should exist.

    The two test is combine to maintain no runners in the application after the
    test.
    """
    # Rename since the app will have a runner.
    app = app_no_runner

    unit = app.units[0]

    # 1.
    exit_code, _ = run_in_unit(unit, f"rm -rf {GithubRunnerCharm.ram_pool_path}")
    assert exit_code == 0

    await app.set_config({"virtual-machines": "1"})

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    await wait_till_num_of_runners(unit, 1)

    # 2.
    await app.set_config({"virtual-machines": "0"})

    action = await unit.run_action("reconcile-runners")
    await action.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    await wait_till_num_of_runners(unit, 0)
