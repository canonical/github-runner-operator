# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with no runner."""
import logging

import pytest
from juju.application import Application
from juju.model import Model

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME
from manager_service import GITHUB_RUNNER_MANAGER_SERVICE_NAME
from tests.integration.helpers.common import reconcile, run_in_unit, wait_for
from tests.integration.helpers.openstack import OpenStackInstanceHelper

logger = logging.getLogger(__name__)

REPO_POLICY_COMPLIANCE_VER_0_2_GIT_SOURCE = (
    "git+https://github.com/canonical/"
    "repo-policy-compliance@48b36c130b207278d20c3847ce651ac13fb9e9d7"
)

pytestmark = pytest.mark.openstack


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_check_runners_no_runners(app_no_runner: Application) -> None:
    """
    arrange: A working application with no runners.
    act: Run check-runners action.
    assert: Action returns result with no runner.
    """
    unit = app_no_runner.units[0]

    action = await unit.run_action("check-runners")
    await action.wait()

    assert action.results["online"] == "0"
    assert action.results["offline"] == "0"
    assert action.results["unknown"] == "0"
    assert action.results["runners"] == "()"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_reconcile_runners(
    model: Model,
    app_no_runner: Application,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with no runners.
    act:
        1.  a. Set virtual-machines config to 1.
            b. Run reconcile_runners action.
        2.  a. Set virtual-machines config to 0.
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
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})

    await reconcile(app=app, model=model)

    async def _runners_number(number) -> bool:
        """Check if there is the expected number of runners."""
        return len(await instance_helper.get_runner_names(unit)) == number

    await wait_for(lambda: _runners_number(1), timeout=10 * 60, check_interval=10)

    # 2.
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})

    await reconcile(app=app, model=model)

    await wait_for(lambda: _runners_number(0), timeout=10 * 60, check_interval=10)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_manager_service_started(
    app_no_runner: Application,
) -> None:
    """
    arrange: A working application with no runners.
    act: Check the github runner manager service.
    assert: The service should be running.
    """
    app = app_no_runner
    unit = app.units[0]

    await run_in_unit(
        unit,
        f"sudo systemctl status {GITHUB_RUNNER_MANAGER_SERVICE_NAME}",
        timeout=60,
        assert_on_failure=True,
        assert_msg="GitHub runner manager service not healthy",
    )
