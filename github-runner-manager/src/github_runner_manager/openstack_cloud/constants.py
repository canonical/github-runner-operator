#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Common constants for the Openstack cloud module."""
from pathlib import Path

RUNNER_LISTENER_PROCESS = "Runner.Listener"
RUNNER_WORKER_PROCESS = "Runner.Worker"

METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
RUNNER_INSTALLED_TS_FILE_NAME = METRICS_EXCHANGE_PATH / "runner-installed.timestamp"
PRE_JOB_METRICS_FILE_NAME = METRICS_EXCHANGE_PATH / "pre-job-metrics.json"
POST_JOB_METRICS_FILE_NAME = METRICS_EXCHANGE_PATH / "post-job-metrics.json"

CREATE_SERVER_TIMEOUT = 5 * 60
