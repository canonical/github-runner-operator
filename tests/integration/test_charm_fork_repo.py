# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo."""

from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
import pytest_asyncio
import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from tests.integration.helpers import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    ensure_charm_has_runner,
    get_runner_names,
    reconcile,
    run_in_unit,
    start_test_http_server,
    wait_until_runner_is_used_up,
)

REPO_POLICY_PORT = 8080
REPO_POLICY_CHECK_MOCK_FAILURE = "The check failed!"
REPO_POLICY_SERVER_MOCK_FILE = "/home/ubuntu/server.py"
REPO_POLICY_SERVER_MOCK = f"""from http.server import BaseHTTPRequestHandler, HTTPServer

class RepoPolicyMockHandler(BaseHTTPRequestHandler):
   def do_POST(self):
       self.send_response(403)
       self.send_header('Content-type', 'text/plain')
       self.end_headers()
       self.wfile.write(b'{REPO_POLICY_CHECK_MOCK_FAILURE}')

httpd = HTTPServer(('0.0.0.0', {REPO_POLICY_PORT}), RepoPolicyMockHandler)
httpd.serve_forever()"""


@pytest_asyncio.fixture(scope="module", name="app_on_forked_repo")
async def app_on_forked_repo_fixture(
    model: Model, app_no_runner: Application, forked_github_repository: Repository
) -> AsyncIterator[Application]:
    """Application with a single runner on the forked repository."""
    app = app_no_runner  # alias for readability as the app will have a runner during the test

    await app.set_config({"path": forked_github_repository.full_name})
    await ensure_charm_has_runner(app=app, model=model)

    yield app


async def _replace_repo_policy_check(unit: Unit) -> None:
    """Replace the repo policy check with a mock that always fails.

    Args:
        unit: The unit to replace the check in.
    """
    await run_in_unit(unit, "/usr/bin/systemctl stop repo-policy-compliance")

    await run_in_unit(
        unit,
        f"cat <<EOT >> {REPO_POLICY_SERVER_MOCK_FILE}\n{REPO_POLICY_SERVER_MOCK}",
    )
    await start_test_http_server(
        unit=unit, port=REPO_POLICY_PORT, exec_start=f"python3 {REPO_POLICY_SERVER_MOCK_FILE}"
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_repo_policy_failure(
    app_on_forked_repo: Application,
    forked_github_repository: Repository,
    forked_github_branch: Branch,
) -> None:
    """
    arrange:
        1. A working application with one runner on the forked repository.
        2. Replace the repo policy check to fail.
    act: Trigger a workflow dispatch on a branch in the forked repository.
    assert: The workflow that was dispatched failed and the reason is logged.
    """
    start_time = datetime.now(timezone.utc)

    unit = app_on_forked_repo.units[0]
    await _replace_repo_policy_check(unit)

    runners = await get_runner_names(unit)
    assert len(runners) == 1
    runner_to_be_used = runners[0]

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
    )

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(forked_github_branch, {"runner": app_on_forked_repo.name})

    await wait_until_runner_is_used_up(unit=unit, runner_name=runner_to_be_used)

    # Unable to find the run id of the workflow that was dispatched.
    # Therefore, all runs after this test start should pass the conditions.
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        if start_time > run.created_at:
            continue

        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if f"Job is about to start running on the runner: {app_on_forked_repo.name}-" in logs:
            assert run.jobs()[0].conclusion == "failure"
            assert (
                "Stopping execution of jobs due to repository setup is not compliant with policies"
                in logs
            )
            assert REPO_POLICY_CHECK_MOCK_FAILURE in logs
            assert "Should not echo if pre-job script failed" not in logs


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_path_config_change(
    model: Model,
    app_on_forked_repo: Application,
    github_repository: Repository,
    path: str,
) -> None:
    """
    arrange: A working application with one runner in a forked repository.
    act: Change the path configuration to the main repository and reconcile runners.
    assert: No runners connected to the forked repository and one runner in the main repository.
    """
    unit = app_on_forked_repo.units[0]

    await app_on_forked_repo.set_config({"path": path})

    await reconcile(app=app_on_forked_repo, model=model)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
