# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for reactive mode functionality."""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import docker
import openstack
import pytest
import yaml
from github.Branch import Branch
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from kombu import Connection

from github_runner_manager import constants
from github_runner_manager.reactive.consumer import JobDetails

from .application import RunningApplication
from .factories import (
    GitHubConfig,
    OpenStackConfig,
    ProxyConfig,
    ReactiveConfig,
    TestConfig,
    create_default_config,
)
from .github_helpers import (
    dispatch_workflow,
    get_workflow_dispatch_run,
    wait_for_workflow_completion,
)

logger = logging.getLogger(__name__)

DISPATCH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_test.yaml"
DISPATCH_CRASH_TEST_WORKFLOW_FILENAME = "workflow_dispatch_crash_test.yaml"
MONGODB_PORT = 27017


def _setup_runner_manager_user() -> None:
    """Create the runner-manager user and required directories (matching charm setup)."""
    result = subprocess.run(
        ["/usr/bin/id", constants.RUNNER_MANAGER_USER],
        check=False,
        capture_output=True,
    )

    if result.returncode != 0:
        logger.info("Creating user %s", constants.RUNNER_MANAGER_USER)
        subprocess.run(
            [
                "/usr/bin/sudo",
                "/usr/sbin/useradd",
                "--system",
                "--create-home",
                "--user-group",
                constants.RUNNER_MANAGER_USER,
            ],
            check=True,
        )

    ssh_dir = Path(f"/home/{constants.RUNNER_MANAGER_USER}/.ssh")
    subprocess.run(["/usr/bin/sudo", "/usr/bin/mkdir", "-p", str(ssh_dir)], check=True)
    subprocess.run(
        [
            "/usr/bin/sudo",
            "/usr/bin/chown",
            "-R",
            f"{constants.RUNNER_MANAGER_USER}:{constants.RUNNER_MANAGER_USER}",
            str(ssh_dir),
        ],
        check=True,
    )
    subprocess.run(["/usr/bin/sudo", "/usr/bin/chmod", "700", str(ssh_dir)], check=True)

    # Add runner-manager user to syslog group for /var/log write access
    subprocess.run(
        [
            "/usr/bin/sudo",
            "/usr/sbin/usermod",
            "-a",
            "-G",
            "syslog",
            constants.RUNNER_MANAGER_USER,
        ],
        check=True,
    )
    subprocess.run(["/usr/bin/sudo", "/usr/bin/chmod", "g+w", "/var/log"], check=True)

    # Pre-create reactive_runner log directory with proper permissions
    # Owned by runner-manager user with syslog group
    reactive_log_dir = Path("/var/log/reactive_runner")
    subprocess.run(["/usr/bin/sudo", "/usr/bin/mkdir", "-p", str(reactive_log_dir)], check=True)
    subprocess.run(["/usr/bin/sudo", "/usr/bin/chmod", "775", str(reactive_log_dir)], check=True)
    subprocess.run(
        [
            "/usr/bin/sudo",
            "/usr/bin/chown",
            f"{constants.RUNNER_MANAGER_USER}:syslog",
            str(reactive_log_dir),
        ],
        check=True,
    )


@pytest.fixture(scope="session")
def mongodb_uri() -> Iterator[str]:
    """Start a MongoDB container for the test session.

    Yields:
        MongoDB connection URI.
    """
    client = docker.from_env()
    container_name = "test-mongodb-reactive"

    try:
        existing = client.containers.get(container_name)
        existing.remove(force=True)
    except docker.errors.NotFound:
        pass

    logger.info("Starting MongoDB container for reactive tests")
    container = client.containers.run(
        "mongo:7.0",
        name=container_name,
        ports={f"{MONGODB_PORT}/tcp": MONGODB_PORT},
        detach=True,
        remove=True,
    )

    # Wait for MongoDB to be ready
    mongodb_connection_uri = f"mongodb://localhost:{MONGODB_PORT}"
    max_retries = 30
    for i in range(max_retries):
        try:
            with Connection(mongodb_connection_uri) as conn:
                conn.connect()
                logger.info("MongoDB is ready")
                break
        except Exception as e:
            if i == max_retries - 1:
                container.stop()
                raise RuntimeError(f"MongoDB failed to start: {e}") from e
            time.sleep(1)

    yield mongodb_connection_uri

    logger.info("Stopping MongoDB container")
    container.stop()


@pytest.fixture(scope="function")
def reactive_application(
    tmp_path_factory: pytest.TempPathFactory,
    mongodb_uri: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    proxy_config: ProxyConfig | None,
    test_config: TestConfig,
) -> Iterator[RunningApplication]:
    """Start the github-runner-manager application in reactive mode.

    Args:
        tmp_path_factory: Pytest temp path factory for creating temp directories.
        mongodb_uri: MongoDB connection URI.
        github_config: GitHub configuration.
        openstack_config: OpenStack configuration.
        proxy_config: Proxy configuration.
        test_config: Test configuration with unique identifiers.

    Yields:
        Running application instance.
    """
    # Create runner-manager user and setup permissions (matching charm setup)
    _setup_runner_manager_user()

    # Clear the queue before starting
    clear_queue(mongodb_uri, test_config.runner_name)
    assert_queue_is_empty(mongodb_uri, test_config.runner_name)

    tmp_test_dir = tmp_path_factory.mktemp("reactive-test")
    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        reactive_config=ReactiveConfig(
            mq_uri=mongodb_uri,
            queue_name=test_config.runner_name,
            max_total_virtual_machines=1,
        ),
    )

    config_path = tmp_test_dir / "config.yaml"
    config_path.write_text(yaml.dump(config))

    metrics_log_path = test_config.debug_log_dir / f"metrics-{test_config.test_id}.log"
    log_file_path = test_config.debug_log_dir / f"app-{test_config.test_id}.log"

    app = RunningApplication.create(
        config_file_path=config_path,
        metrics_log_path=metrics_log_path,
        log_file_path=log_file_path,
    )

    # Wait for application to start
    time.sleep(5)

    yield app

    logger.info("Stopping reactive application")
    app.stop()

    # Clean up queue after test
    clear_queue(mongodb_uri, test_config.runner_name)


def create_job_details(run: WorkflowRun, labels: set[str]) -> JobDetails:
    """Create a JobDetails object from a workflow run.

    Args:
        run: The workflow run containing the job.
        labels: The labels for the job.

    Returns:
        JobDetails object with job URL and labels.
    """
    jobs = list(run.jobs())
    assert len(jobs) == 1, "Expected 1 job to be created"
    job = jobs[0]
    return JobDetails(labels=labels, url=job.url)


def add_to_queue(msg: str, mongodb_uri: str, queue_name: str) -> None:
    """Add a message to the queue.

    Args:
        msg: The message to add.
        mongodb_uri: MongoDB connection URI.
        queue_name: Name of the queue.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.put(msg, retry=True)


def clear_queue(mongodb_uri: str, queue_name: str) -> None:
    """Clear all messages from the queue.

    Args:
        mongodb_uri: MongoDB connection URI.
        queue_name: Name of the queue.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            simple_queue.clear()


def assert_queue_is_empty(mongodb_uri: str, queue_name: str) -> None:
    """Assert that the queue is empty.

    Args:
        mongodb_uri: MongoDB connection URI.
        queue_name: Name of the queue.
    """
    assert_queue_has_size(mongodb_uri, queue_name, 0)


def assert_queue_has_size(mongodb_uri: str, queue_name: str, size: int) -> None:
    """Assert that the queue has the expected size.

    Args:
        mongodb_uri: MongoDB connection URI.
        queue_name: Name of the queue.
        size: Expected size of the queue.
    """
    queue_size = get_queue_size(mongodb_uri, queue_name)
    assert queue_size == size, f"Queue {queue_name} expected size: {size}, actual: {queue_size}"


def get_queue_size(mongodb_uri: str, queue_name: str) -> int:
    """Get the current size of the queue.

    Args:
        mongodb_uri: MongoDB connection URI.
        queue_name: Name of the queue.

    Returns:
        Number of messages in the queue.
    """
    with Connection(mongodb_uri) as conn:
        with conn.SimpleQueue(queue_name) as simple_queue:
            return simple_queue.qsize()


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("reactive_application")
def test_reactive_mode_spawns_runner(
    mongodb_uri: str,
    github_repository: Repository,
    github_branch: Branch,
    test_config: TestConfig,
):
    """
    arrange: Place a message in the queue and dispatch a workflow.
    act: Application consumes the message and spawns a runner.
    assert: Runner processes the job and the message is removed from the queue.
    """
    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    run = get_workflow_dispatch_run(
        workflow=workflow,
        ref=github_branch,
        dispatch_time=dispatch_time,
    )

    labels = set(test_config.labels + ["x64"])
    job = create_job_details(run=run, labels=labels)
    add_to_queue(
        json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
        mongodb_uri,
        test_config.runner_name,
    )

    try:
        wait_for_workflow_completion(run, timeout=600)
    except TimeoutError:
        pytest.fail("Job did not complete successfully. Check logs for infrastructure issues.")

    run.update()
    assert run.conclusion == "success"
    assert_queue_is_empty(mongodb_uri, test_config.runner_name)


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("reactive_application")
def test_reactive_mode_with_not_found_job(
    mongodb_uri: str,
    test_config: TestConfig,
):
    """
    arrange: Place a message with a non-existent job URL in the queue.
    act: Application consumes the message.
    assert: The message is removed from the queue without spawning a runner.
    """
    labels = set(test_config.labels + ["x64"])
    job = JobDetails(
        labels=labels,
        url="https://github.com/canonical/github-runner-operator/actions/runs/mock-run/job/mock-job",
    )
    add_to_queue(
        json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
        mongodb_uri,
        test_config.runner_name,
    )

    max_wait = 30
    for _ in range(max_wait):
        if get_queue_size(mongodb_uri, test_config.runner_name) == 0:
            break
        time.sleep(1)

    assert_queue_is_empty(mongodb_uri, test_config.runner_name)


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("reactive_application")
def test_reactive_mode_does_not_consume_jobs_with_unsupported_labels(
    mongodb_uri: str,
    github_repository: Repository,
    github_branch: Branch,
    test_config: TestConfig,
):
    """
    arrange: Place a message with unsupported labels in the queue and dispatch a workflow.
    act: Application consumes the message.
    assert: No runner is spawned and the message is removed from the queue.
    """
    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    run = get_workflow_dispatch_run(
        workflow=workflow,
        ref=github_branch,
        dispatch_time=dispatch_time,
    )

    job = create_job_details(run=run, labels={"not supported label"})
    add_to_queue(
        job.json(),
        mongodb_uri,
        test_config.runner_name,
    )

    # Wait for message to be consumed
    max_wait = 30
    for _ in range(max_wait):
        if get_queue_size(mongodb_uri, test_config.runner_name) == 0:
            break
        time.sleep(1)

    try:
        assert_queue_is_empty(mongodb_uri, test_config.runner_name)
        run.update()
        assert run.status == "queued"
    finally:
        run.cancel()


@pytest.mark.abort_on_fail
def test_reactive_mode_graceful_shutdown(
    tmp_path_factory: pytest.TempPathFactory,
    mongodb_uri: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    proxy_config: ProxyConfig | None,
    test_config: TestConfig,
    github_repository: Repository,
    github_branch: Branch,
    openstack_connection: openstack.connection.Connection,
):
    """
    arrange: Start application with max_size=2, dispatch a workflow, and add job to queue.
    act:
        1. Stop the application while runner is processing the job.
        2. Start new application with max_size=0 and dispatch another workflow.
    assert:
        1. The first job may succeed or fail depending on timing.
        2. The second job remains queued and there is a message in the queue.
    """
    tmp_test_dir = tmp_path_factory.mktemp("reactive-shutdown-test")
    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        reactive_config=ReactiveConfig(
            mq_uri=mongodb_uri,
            queue_name=test_config.runner_name,
            max_total_virtual_machines=2,
        ),
    )

    config_path = tmp_test_dir / "config.yaml"
    config_path.write_text(yaml.dump(config))

    clear_queue(mongodb_uri, test_config.runner_name)

    app = RunningApplication.create(config_file_path=config_path)
    time.sleep(5)

    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    run = get_workflow_dispatch_run(
        workflow=workflow,
        ref=github_branch,
        dispatch_time=dispatch_time,
    )
    job = create_job_details(run=run, labels=set(test_config.labels))
    add_to_queue(
        job.json(),
        mongodb_uri,
        test_config.runner_name,
    )

    # Wait for job to start
    max_wait = 120
    for _ in range(max_wait):
        run.update()
        if run.status == "in_progress":
            break
        time.sleep(1)

    # Wait a bit for the runner to start processing
    time.sleep(10)

    # Stop the application (simulating scale down)
    logger.info("Stopping application to test graceful shutdown")
    app.stop()

    # Job may complete or fail depending on timing
    try:
        wait_for_workflow_completion(run, timeout=300)
    except TimeoutError:
        pass

    run.update()
    logger.info("First job status after shutdown: %s, conclusion: %s", run.status, run.conclusion)

    # Verify all runners are cleaned up after scale down
    max_wait = 60
    for _ in range(max_wait):
        servers = [
            server
            for server in openstack_connection.list_servers()
            if server.name.startswith(test_config.vm_prefix)
        ]
        if not servers:
            break
        time.sleep(1)

    remaining_servers = [
        server
        for server in openstack_connection.list_servers()
        if server.name.startswith(test_config.vm_prefix)
    ]
    assert not remaining_servers, (
        f"Expected all runners to be cleaned up after scale down, "
        f"but found: {[s.name for s in remaining_servers]}"
    )

    clear_queue(mongodb_uri, test_config.runner_name)

    # Start new application with max_size=0
    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        reactive_config=ReactiveConfig(
            mq_uri=mongodb_uri,
            queue_name=test_config.runner_name,
            max_total_virtual_machines=0,
        ),
    )
    config_path.write_text(yaml.dump(config))

    app2 = RunningApplication.create(config_file_path=config_path)
    time.sleep(5)

    dispatch_time2 = datetime.now(timezone.utc)
    workflow2 = dispatch_workflow(
        repository=github_repository,
        workflow_filename=DISPATCH_CRASH_TEST_WORKFLOW_FILENAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    run2 = get_workflow_dispatch_run(
        workflow=workflow2,
        ref=github_branch,
        dispatch_time=dispatch_time2,
    )
    job2 = create_job_details(run=run2, labels=set(test_config.labels))
    add_to_queue(
        job2.json(),
        mongodb_uri,
        test_config.runner_name,
    )

    # Wait a bit for potential processing
    time.sleep(10)

    run2.update()
    assert run2.status == "queued"
    run2.cancel()

    assert_queue_has_size(mongodb_uri, test_config.runner_name, 1)

    app2.stop()

    # Verify no runners were spawned with max_size=0
    servers = [
        server
        for server in openstack_connection.list_servers()
        if server.name.startswith(test_config.vm_prefix)
    ]
    assert not servers, (
        f"Expected no runners to be spawned with max_size=0, "
        f"but found: {[s.name for s in servers]}"
    )

    clear_queue(mongodb_uri, test_config.runner_name)
