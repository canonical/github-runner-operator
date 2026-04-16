# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm containing one runner."""

from typing import Iterator

import jubilant
import pytest
from github.Branch import Branch
from github.Repository import Repository

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME, OTEL_COLLECTOR_ENDPOINT_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    get_job_logs,
    wait_for,
    wait_for_runner_ready,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper


@pytest.fixture(scope="function", name="app")
def app_fixture(
    juju: jubilant.Juju,
    basic_app: str,
) -> Iterator[str]:
    """Setup and teardown the charm after each test.

    Ensure the charm has no runner after a test.
    """
    yield basic_app

    juju.config(basic_app, values={BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})

    unit_name = f"{basic_app}/0"

    def _no_runners() -> bool:
        """Check that no runners are active."""
        try:
            result = juju.run(unit_name, "check-runners")
        except (jubilant.CLIError, TimeoutError):
            return False
        return (
            result.status == "completed"
            and result.results["online"] == "0"
            and result.results["offline"] == "0"
            and result.results["unknown"] == "0"
        )

    wait_for(_no_runners, timeout=10 * 60, check_interval=10)


@pytest.mark.openstack
@pytest.mark.abort_on_fail
def test_check_runner(
    juju: jubilant.Juju, app: str, instance_helper: OpenStackInstanceHelper
) -> None:
    """
    arrange: A working application with one runner.
    act: Run check_runner action.
    assert: Action returns result with one runner.
    """
    instance_helper.set_app_runner_amount(app, 2)

    result = juju.run(f"{app}/0", "check-runners")

    assert result.status == "completed"
    assert result.results["online"] == "2"
    assert result.results["offline"] == "0"
    assert result.results["unknown"] == "0"


@pytest.mark.openstack
@pytest.mark.abort_on_fail
def test_flush_runner_and_resource_config(
    juju: jubilant.Juju,
    app: str,
    github_repository: Repository,
    test_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with two runners.
    act:
        1. Run Check_runner action. Record the runner names for later.
        2. Flush runners.
        3. Dispatch a workflow to make runner busy and call flush_runner action.

    assert:
        1. Two runner exists.
        2. Runners are recreated.
        3. The runner is not flushed since by default it flushes idle.

    Test are combined to reduce number of runner spawned.
    """
    instance_helper.ensure_charm_has_runner(app)

    unit_name = f"{app}/0"

    # 1.
    result = juju.run(unit_name, "check-runners")

    assert result.status == "completed"
    assert result.results["online"] == "1"
    assert result.results["offline"] == "0"
    assert result.results["unknown"] == "0"

    runner_names = result.results["runners"].split(", ")
    assert len(runner_names) == 1

    # 2.
    juju.run(unit_name, "flush-runners")

    wait_for_runner_ready(juju, app)

    result = juju.run(unit_name, "check-runners")

    assert result.status == "completed"
    assert result.results["online"] == "1"
    assert result.results["offline"] == "0"
    assert result.results["unknown"] == "0"

    new_runner_names = result.results["runners"].split(", ")
    assert len(new_runner_names) == 1
    assert new_runner_names[0] != runner_names[0]

    # 3.
    workflow = dispatch_workflow(
        app_name=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": app, "minutes": "5"},
        wait=False,
    )
    wait_for(lambda: workflow.update() or workflow.status == "in_progress")
    result = juju.run(unit_name, "flush-runners")

    assert result.status == "completed"


@pytest.mark.openstack
@pytest.mark.abort_on_fail
def test_custom_pre_job_script(
    juju: jubilant.Juju,
    app: str,
    github_repository: Repository,
    test_github_branch: Branch,
) -> None:
    """
    arrange: A working application with one runner with a custom pre-job script enabled.
    act: Dispatch a workflow.
    assert: Workflow run successfully passed and pre-job script has been executed.
    """
    juju.config(
        app,
        values={
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME: """
#!/usr/bin/env bash
cat > ~/.ssh/config <<EOF
host github.com
  user git
  hostname github.com
  port 22
  proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128
EOF
logger -s "SSH config: $(cat ~/.ssh/config)"
    """,
        },
    )
    wait_for_runner_ready(juju, app)

    workflow_run = dispatch_workflow(
        app_name=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": app},
    )
    logs = get_job_logs(workflow_run.jobs("latest")[0])
    assert "SSH config" in logs
    assert "proxycommand socat - PROXY:squid.internal:%h:%p,proxyport=3128" in logs


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_otel_collector_endpoint_pre_job_installs_config(
    app: Application,
    github_repository: Repository,
    test_github_branch: Branch,
    instance_helper: OpenStackInstanceHelper,
) -> None:
    """
    arrange: A working application with one runner and otel collector endpoint configured.
    act: Dispatch a workflow to run pre-job script.
    assert: The workflow writes otel collector config to /etc/otelcol/config.d/github.yaml.
    """
    endpoint = "10.10.0.12:4317"
    await app.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1",
            OTEL_COLLECTOR_ENDPOINT_CONFIG_NAME: endpoint,
        }
    )
    await wait_for_runner_ready(app)

    await dispatch_workflow(
        app=app,
        branch=test_github_branch,
        github_repository=github_repository,
        conclusion="success",
        workflow_id_or_name=DISPATCH_TEST_WORKFLOW_FILENAME,
        dispatch_input={"runner": app.name},
    )

    exit_code, stdout, stderr = await instance_helper.run_in_instance(
        unit=app.units[0],
        command="sudo cat /etc/otelcol/config.d/github.yaml",
    )

    assert exit_code == 0, stderr
    assert stdout is not None
    assert "exporters:" in stdout
    assert f"endpoint: {endpoint}" in stdout
