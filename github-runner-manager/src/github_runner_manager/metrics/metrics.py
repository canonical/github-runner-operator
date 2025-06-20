#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""A module for managing runner metrics after run completion."""

from typing import Sequence

from github_runner_manager.cloud.openstack import CloudVM


class MetricsProvider:
    """A class to provide metrics for runners."""

    def propagate_metrics(self, vms: Sequence[CloudVM]) -> None:
        """Propagate metrics from completed OpenStack VMs."""
        ...
