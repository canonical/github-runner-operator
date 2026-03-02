# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Application-level integration tests for runner metrics events."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import openstack
import pytest
import yaml
from github.Branch import Branch
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github_runner_manager.manager.vm_manager import PostJobStatus
from openstack.compute.v2.server import Server as OpenstackServer

from .application import RunningApplication
from .factories import (
    GitHubConfig,
    OpenStackConfig,
    ProxyConfig,
    TestConfig,
    create_default_config,
)
from .github_helpers import (
    dispatch_workflow,
    get_workflow_dispatch_run,
    wait_for_workflow_completion,
)
from .metrics_helpers import (
    assert_events_after_reconciliation,
    clear_metrics_log,
    wait_for_events,
    wait_for_runner_to_be_marked_offline,
)
from .openstack_helpers import resolve_runner_ssh_key_path, wait_for_no_runners, wait_for_runner
from .planner_stub import PlannerStub, PlannerStubConfig

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
RUNNER_CRASH_WAIT_SECONDS = 10


def _wait_for_workflow_status(
    workflow_run: WorkflowRun,
    status: str,
    timeout: int = 15 * 60,
    interval: int = 10,
) -> bool:
    """Wait for a workflow run to reach the target status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        workflow_run.update()
        if workflow_run.status == status:
            return True
        time.sleep(interval)
    return False


def _kill_run_script(runner: OpenstackServer, runner_ip: str) -> None:
    """Kill actions-runner run.sh inside a runner VM."""
    key_path = resolve_runner_ssh_key_path(runner)
    result = subprocess.run(
        [
            "/usr/bin/ssh",
            "-i",
            str(key_path),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{runner_ip}",
            "pkill -9 run.sh",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Failed to kill run.sh: {result.stderr}"


@pytest.fixture
def metrics_planner_stub(test_config: TestConfig) -> Iterator[PlannerStub]:
    """Start a planner stub compatible with this module's flavor name."""
    stub = PlannerStub(
        PlannerStubConfig(initial_pressure=1, flavor_name=test_config.runner_name)
    )
    stub.start()
    try:
        yield stub
    finally:
        stub.stop()


@pytest.fixture
def planner_app_with_metrics(
    tmp_test_dir: Path,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    proxy_config: ProxyConfig | None,
    metrics_planner_stub: PlannerStub,
) -> Iterator[tuple[RunningApplication, PlannerStub, Path]]:
    """Start app + planner stub for metrics tests with metrics log persisted to disk."""
    run_id = time.time_ns()
    metrics_planner_stub.set_pressure(1)

    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        planner_url=metrics_planner_stub.base_url,
        planner_token=metrics_planner_stub.token,
        reconcile_interval=1,
        base_virtual_machines=0,
    )

    config_path = tmp_test_dir / f"metrics-config-{run_id}.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    metrics_log_path = tmp_test_dir / f"github-runner-metrics-{run_id}.log"
    log_file_path = test_config.debug_log_dir / f"metrics-app-{test_config.test_id}-{run_id}.log"
    app = RunningApplication.create(
        config_file_path=config_path,
        metrics_log_path=metrics_log_path,
        log_file_path=log_file_path,
    )

    try:
        yield app, metrics_planner_stub, metrics_log_path
    finally:
        metrics_planner_stub.set_pressure(0)
        wait_for_no_runners(openstack_connection, test_config, timeout=15 * 60)
        app.stop()


def test_runner_installed_metric(
    planner_app_with_metrics: tuple[RunningApplication, PlannerStub, Path],
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
) -> None:
    """Assert `runner_installed` metric is issued for an installed runner."""
    _, stub, metrics_log_path = planner_app_with_metrics
    clear_metrics_log(metrics_log_path)

    runner, _ = wait_for_runner(openstack_connection, test_config, timeout=10 * 60)
    assert runner is not None, "Runner did not appear within timeout"

    stub.set_pressure(0)
    cleaned = wait_for_no_runners(openstack_connection, test_config, timeout=15 * 60)
    assert cleaned, "Runner was not cleaned up after setting pressure to 0"

    events = wait_for_events(metrics_log_path, {"runner_installed"}, timeout=5 * 60)
    runner_installed_events = [
        event for event in events if event.get("event") == "runner_installed"
    ]
    assert runner_installed_events, "runner_installed event has not been logged"
    for metric in runner_installed_events:
        assert metric.get("flavor") == test_config.runner_name
        assert metric.get("duration") >= 0


def test_metrics_after_workflow_completion(
    planner_app_with_metrics: tuple[RunningApplication, PlannerStub, Path],
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    github_repository: Repository,
    github_branch: Branch,
) -> None:
    """Assert normal runner start/stop/reconciliation metrics after a successful workflow."""
    _, stub, metrics_log_path = planner_app_with_metrics
    clear_metrics_log(metrics_log_path)

    runner, _ = wait_for_runner(openstack_connection, test_config, timeout=10 * 60)
    assert runner is not None, "Runner did not appear within timeout"

    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    workflow_run = get_workflow_dispatch_run(
        workflow=workflow, ref=github_branch, dispatch_time=dispatch_time
    )
    assert _wait_for_workflow_status(workflow_run, "in_progress"), "Workflow never started running"
    assert wait_for_workflow_completion(workflow_run, timeout=20 * 60), (
        "Workflow did not complete or timed out."
    )
    assert workflow_run.conclusion == "success"

    stub.set_pressure(0)
    cleaned = wait_for_no_runners(openstack_connection, test_config, timeout=15 * 60)
    assert cleaned, "Runner was not cleaned up after setting pressure to 0"

    events = wait_for_events(metrics_log_path, {"runner_start", "runner_stop", "reconciliation"})
    assert_events_after_reconciliation(
        events=events,
        flavor=test_config.runner_name,
        github_repository=github_repository,
        post_job_status=PostJobStatus.NORMAL,
    )


def test_metrics_for_abnormal_termination(
    planner_app_with_metrics: tuple[RunningApplication, PlannerStub, Path],
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    github_repository: Repository,
    github_branch: Branch,
) -> None:
    """Assert abnormal status metrics when run.sh is terminated in the runner VM."""
    _, stub, metrics_log_path = planner_app_with_metrics
    clear_metrics_log(metrics_log_path)

    runner, runner_ip = wait_for_runner(openstack_connection, test_config, timeout=10 * 60)
    assert runner is not None and runner_ip, "Runner did not appear within timeout"

    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    workflow_run = get_workflow_dispatch_run(
        workflow=workflow, ref=github_branch, dispatch_time=dispatch_time
    )
    assert _wait_for_workflow_status(workflow_run, "in_progress"), "Workflow never started running"

    # Let the runner fully enter job execution before terminating run.sh.
    time.sleep(RUNNER_CRASH_WAIT_SECONDS)
    _kill_run_script(runner, runner_ip)
    workflow_run.cancel()
    wait_for_runner_to_be_marked_offline(github_repository, runner.name, timeout=20 * 60)

    stub.set_pressure(0)
    cleaned = wait_for_no_runners(openstack_connection, test_config, timeout=15 * 60)
    assert cleaned, "Runner was not cleaned up after setting pressure to 0"

    events = wait_for_events(metrics_log_path, {"runner_start", "runner_stop", "reconciliation"})
    assert_events_after_reconciliation(
        events=events,
        flavor=test_config.runner_name,
        github_repository=github_repository,
        post_job_status=PostJobStatus.ABNORMAL,
    )
