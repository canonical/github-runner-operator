#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for metrics."""
import json
import logging
from time import sleep

import requests
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from metrics import METRICS_LOG_PATH
from tests.integration.helpers import create_runner, DISPATCH_TEST_WORKFLOW_FILENAME, \
    get_runner_names, run_in_unit
from tests.status_name import ACTIVE_STATUS_NAME


async def _get_metrics_log(unit: Unit) -> str:
    """Retrieve the metrics log from the unit.

    Args:
        unit: The unit to retrieve the metrics log from.

    Returns:
        The metrics log.
    """
    retcode, stdout = await run_in_unit(
            unit=unit, command=f"if [ -f {METRICS_LOG_PATH} ]; then cat {METRICS_LOG_PATH}; else echo ''; fi"
        )
    assert retcode == 0, f"Failed to get metrics log: {stdout}"
    assert stdout is not None, "Failed to get metrics log, no stdout message"
    return stdout.strip()


# async def test_charm_issues_runner_installed_metric(
#     model: Model,
#     app_no_runner: Application,
# ):
#     """
#     arrange: A charm without runners integrated with grafana-agent using the cos-agent integration.
#     act: Config the charm to contain one runner.
#     assert: The RunnerInstalled metric is logged.
#     """
#     app = app_no_runner  # alias for readability as the app will have a runner during the test
#     grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
#     await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
#     await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)
#     await model.wait_for_idle(apps=[grafana_agent.name])
#     metrics_log = await _get_metrics_log(app.units[0])
#     assert metrics_log == "".strip()
#
#     await create_runner(app=app, model=model)
#
#     metrics_log = await _get_metrics_log(app.units[0])
#     logging.info("Metric log: %s", metrics_log)
#     metric_log = json.loads(metrics_log)
#     assert metric_log.get("flavor") == app.name
#     assert metric_log.get("event") == "runner_installed"
#     assert metric_log.get("duration") >= 0


async def test_charm_issues_runner_metrics(
        model: Model,
        app_no_runner: Application,
        forked_github_repository: Repository,
        forked_github_branch: Branch
):
    app = app_no_runner  # alias for readability as the app will have a runner during the test
    grafana_agent = await model.deploy("grafana-agent", channel="latest/edge")
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)
    await model.wait_for_idle(apps=[grafana_agent.name])
    metrics_log = await _get_metrics_log(app.units[0])
    assert metrics_log == "".strip()

    await app.set_config({"path": forked_github_repository.full_name})
    await create_runner(app=app_no_runner, model=model)

    workflow = forked_github_repository.get_workflow(
        id_or_file_name=DISPATCH_TEST_WORKFLOW_FILENAME
    )

    # The `create_dispatch` returns True on success.
    assert workflow.create_dispatch(
        forked_github_branch, {"runner": app.name}
    )

    # Wait until the runner is used up.
    unit = app.units[0]
    runners = await get_runner_names(unit)
    assert len(runners) == 1
    runner_to_be_used = runners[0]

    for _ in range(30):
        runners = await get_runner_names(unit)
        if runner_to_be_used not in runners:
            break
        sleep(30)
    else:
        assert False, "Timeout while waiting for workflow to complete"

    for run in workflow.get_runs():
        logs_url = run.jobs()[0].logs_url()
        logs = requests.get(logs_url).content.decode("utf-8")

        if (
            f"Job is about to start running on the runner: {app.name}-"
            in logs
        ):
            assert run.jobs()[0].conclusion == "success"

            # Set the number of virtual machines to 0 to speedup reconciliation
            await app.set_config({"virtual-machines": "0"})
            action = await unit.run_action("reconcile-runners")
            await action.wait()
            await model.wait_for_idle(apps=[app.name], status=ACTIVE_STATUS_NAME)

            metrics_log = await _get_metrics_log(unit=unit)
            logging.info("Metric log: %s", metrics_log)
            log_lines = map(lambda line: json.loads(line), metrics_log.splitlines())

            for metric_log in log_lines:
                if metric_log.get("event") == "runner_start":
                    assert metric_log.get("flavor") == app.name
                    assert metric_log.get("workflow") == "Workflow Dispatch Tests"
                    assert metric_log.get("repo") == forked_github_repository.full_name
                    assert metric_log.get("github_event") == "workflow_dispatch"
                    assert metric_log.get("idle") >= 0
                    break
            else:
                assert False, "No runner_start metric found"
