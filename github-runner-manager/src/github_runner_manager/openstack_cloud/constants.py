#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Common constants for the Openstack cloud module."""
from pathlib import Path

RUNNER_LISTENER_PROCESS = "Runner.Listener"
RUNNER_WORKER_PROCESS = "Runner.Worker"
METRICS_EXCHANGE_PATH = Path("/home/ubuntu/metrics-exchange")
CREATE_SERVER_TIMEOUT = 5 * 60
